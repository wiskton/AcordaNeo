"""Gerenciador do Ícone na Bandeja do Sistema (System Tray).

Suporta nativamente:
- Wayland / COSMIC / GNOME Shell (AppIndicator) / KDE Plasma via StatusNotifierItem (DBus).
- Ambientes X11 tradicionais via fallback para Gtk.StatusIcon.
Sem dependências C adicionais além de PyGObject (GIO/GLib/GTK).
"""

import sys
from pathlib import Path
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gio, GLib, Gtk

SNI_XML = """
<node>
  <interface name='org.kde.StatusNotifierItem'>
    <property name='Category' type='s' access='read'/>
    <property name='Id' type='s' access='read'/>
    <property name='Title' type='s' access='read'/>
    <property name='Status' type='s' access='read'/>
    <property name='WindowId' type='i' access='read'/>
    <property name='IconName' type='s' access='read'/>
    <property name='IconThemePath' type='s' access='read'/>
    <property name='IconPixmap' type='a(iiay)' access='read'/>
    <property name='Menu' type='o' access='read'/>
    <property name='ItemIsMenu' type='b' access='read'/>
    <property name='ToolTip' type='(sa(iiay)ss)' access='read'/>
    <method name='Activate'>
      <arg type='i' name='x' direction='in'/>
      <arg type='i' name='y' direction='in'/>
    </method>
    <method name='ContextMenu'>
      <arg type='i' name='x' direction='in'/>
      <arg type='i' name='y' direction='in'/>
    </method>
    <method name='SecondaryActivate'>
      <arg type='i' name='x' direction='in'/>
      <arg type='i' name='y' direction='in'/>
    </method>
    <method name='Scroll'>
      <arg type='i' name='delta' direction='in'/>
      <arg type='s' name='orientation' direction='in'/>
    </method>
    <signal name='NewStatus'>
      <arg type='s' name='status'/>
    </signal>
    <signal name='NewIcon'/>
    <signal name='NewToolTip'/>
  </interface>
</node>
"""

DBUSMENU_XML = """
<node>
  <interface name='com.canonical.dbusmenu'>
    <property name='Version' type='u' access='read'/>
    <property name='TextDirection' type='s' access='read'/>
    <property name='Status' type='s' access='read'/>
    <property name='IconThemePath' type='as' access='read'/>
    <method name='GetLayout'>
      <arg type='i' name='parentId' direction='in'/>
      <arg type='i' name='recursionDepth' direction='in'/>
      <arg type='as' name='propertyNames' direction='in'/>
      <arg type='u' name='revision' direction='out'/>
      <arg type='(ia{sv}av)' name='layout' direction='out'/>
    </method>
    <method name='GetGroupProperties'>
      <arg type='ai' name='ids' direction='in'/>
      <arg type='as' name='propertyNames' direction='in'/>
      <arg type='a(ia{sv})' name='properties' direction='out'/>
    </method>
    <method name='GetProperty'>
      <arg type='i' name='id' direction='in'/>
      <arg type='s' name='name' direction='in'/>
      <arg type='v' name='value' direction='out'/>
    </method>
    <method name='Event'>
      <arg type='i' name='id' direction='in'/>
      <arg type='s' name='eventId' direction='in'/>
      <arg type='v' name='data' direction='in'/>
      <arg type='u' name='timestamp' direction='in'/>
    </method>
    <method name='AboutToShow'>
      <arg type='i' name='id' direction='in'/>
      <arg type='b' name='needUpdate' direction='out'/>
    </method>
    <signal name='LayoutUpdated'>
      <arg type='u' name='revision'/>
      <arg type='i' name='parent'/>
    </signal>
  </interface>
</node>
"""


class TrayManager:
    def __init__(
        self,
        ao_alternar_janela: Callable[[], None],
        ao_abrir_preferencias: Callable[[], None],
        ao_sair: Callable[[], None],
        icone_path: Optional[Path] = None,
        ao_exportar_conversa: Optional[Callable[[], None]] = None,
    ):
        self._ao_alternar = ao_alternar_janela
        self._ao_preferencias = ao_abrir_preferencias
        self._ao_sair = ao_sair
        self._ao_exportar = ao_exportar_conversa
        self._icone_path = icone_path

        self._status_texto = "Diga \"Acorda, Neo\" pra começar"
        self._estado = "escutando"
        self._icone_nome = "acordaneo"
        self._menu_revision = 1
        self._sni_ativo = False
        self._gtk_status_icon = None

        # Carrega pixmaps em múltiplos tamanhos para envio direto ao painel
        self._icon_pixmaps = self._gerar_pixmaps()

        self._iniciar_sni()
        if not self._sni_ativo:
            self._iniciar_fallback_gtk()

    def _gerar_pixmaps(self):
        caminho = self._icone_path or (Path.home() / ".local/share/icons/acordaneo.png")
        if not caminho or not caminho.exists():
            return []
        pixmaps = []
        for tamanho in (22, 24, 32, 48):
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(caminho), tamanho, tamanho, True)
                w, h = pb.get_width(), pb.get_height()
                pixels = pb.get_pixels()
                rowstride = pb.get_rowstride()
                n_channels = pb.get_n_channels()
                argb = bytearray(w * h * 4)
                for y in range(h):
                    for x in range(w):
                        offset = y * rowstride + x * n_channels
                        r = pixels[offset]
                        g = pixels[offset + 1]
                        b = pixels[offset + 2]
                        a = pixels[offset + 3] if n_channels == 4 else 255
                        idx = (y * w + x) * 4
                        argb[idx] = a
                        argb[idx + 1] = r
                        argb[idx + 2] = g
                        argb[idx + 3] = b
                pixmaps.append((w, h, bytes(argb)))
            except Exception:
                pass
        return pixmaps

    def _iniciar_sni(self):
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            sni_node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
            menu_node = Gio.DBusNodeInfo.new_for_xml(DBUSMENU_XML)

            self._sni_reg_id = self._bus.register_object(
                "/StatusNotifierItem",
                sni_node.interfaces[0],
                self._handle_sni_call,
                self._handle_sni_get_property,
                None,
            )

            self._menu_reg_id = self._bus.register_object(
                "/MenuBar",
                menu_node.interfaces[0],
                self._handle_menu_call,
                self._handle_menu_get_property,
                None,
            )

            # Registra no StatusNotifierWatcher da sessão
            self._bus.call_sync(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", ("/StatusNotifierItem",)),
                None,
                Gio.DBusCallFlags.NONE,
                2000,
                None,
            )
            self._sni_ativo = True
            print("[tray] Ícone registrado via DBus StatusNotifierItem (COSMIC/Wayland/GNOME)")
        except Exception as e:
            print(f"[tray] Não foi possível registrar SNI: {e}")
            self._sni_ativo = False

    def _iniciar_fallback_gtk(self):
        try:
            self._gtk_status_icon = Gtk.StatusIcon()
            if self._icone_path and self._icone_path.exists():
                self._gtk_status_icon.set_from_file(str(self._icone_path))
            else:
                self._gtk_status_icon.set_from_icon_name("acordaneo")
            self._gtk_status_icon.set_tooltip_text(f"Acorda, Neo — {self._status_texto}")
            self._gtk_status_icon.connect("activate", lambda *_a: self._ao_alternar())
            self._gtk_status_icon.connect(
                "popup-menu",
                lambda icon, button, time: self._mostrar_menu_gtk(
                    icon=icon, button=button, activate_time=time
                ),
            )
            print("[tray] Fallback ativado com Gtk.StatusIcon")
        except Exception as e:
            print(f"[tray] Fallback Gtk.StatusIcon não disponível: {e}")

    def _mostrar_menu_gtk(self, icon=None, button=3, activate_time=0, x=None, y=None):
        menu = Gtk.Menu()

        item_status = Gtk.MenuItem(label=f"Neo: {self._status_texto}")
        item_status.set_sensitive(False)
        menu.append(item_status)

        menu.append(Gtk.SeparatorMenuItem())

        item_janela = Gtk.MenuItem(label="Mostrar / Ocultar Janela")
        item_janela.connect("activate", lambda *_a: self._ao_alternar())
        menu.append(item_janela)

        item_pref = Gtk.MenuItem(label="Preferências...")
        item_pref.connect("activate", lambda *_a: self._ao_preferencias())
        menu.append(item_pref)

        if self._ao_exportar:
            item_exp = Gtk.MenuItem(label="Exportar Conversa (Markdown)...")
            item_exp.connect("activate", lambda *_a: self._ao_exportar())
            menu.append(item_exp)

        menu.append(Gtk.SeparatorMenuItem())

        item_sair = Gtk.MenuItem(label="Encerrar o aplicativo")
        item_sair.connect("activate", lambda *_a: self._ao_sair())
        menu.append(item_sair)

        menu.show_all()
        if self._gtk_status_icon:
            menu.popup(
                None, None, Gtk.StatusIcon.position_menu, self._gtk_status_icon, button, activate_time
            )
        else:
            menu.popup_at_pointer(None)

    # ----------------------------------------------------------- SNI Handlers

    def _handle_sni_call(self, conn, sender, path, iface, method, params, inv):
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(self._ao_alternar)
        elif method == "ContextMenu":
            x = params[0] if len(params) > 0 else 0
            y = params[1] if len(params) > 1 else 0
            GLib.idle_add(lambda: self._mostrar_menu_gtk(x=x, y=y))
        inv.return_value(None)

    def _handle_sni_get_property(self, conn, sender, path, iface, name):
        props = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "acordaneo"),
            "Title": GLib.Variant("s", "Acorda, Neo"),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", "acordaneo"),
            "IconThemePath": GLib.Variant("s", str(Path.home() / ".local/share/icons")),
            "IconPixmap": GLib.Variant("a(iiay)", self._icon_pixmaps),
            "Menu": GLib.Variant("o", "/MenuBar"),
            "ItemIsMenu": GLib.Variant("b", False),
            "ToolTip": GLib.Variant(
                "(sa(iiay)ss)",
                (
                    "acordaneo",
                    self._icon_pixmaps,
                    "Acorda, Neo",
                    self._status_texto,
                ),
            ),
        }
        return props.get(name)

    # ------------------------------------------------------ DBusMenu Handlers

    def _obter_itens_menu(self):
        status_label = f"Neo: {self._status_texto}"
        itens = {
            100: {
                "label": GLib.Variant("s", status_label),
                "enabled": GLib.Variant("b", False),
                "visible": GLib.Variant("b", True),
            },
            1: {
                "label": GLib.Variant("s", "Mostrar / Ocultar Janela"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            },
            2: {
                "label": GLib.Variant("s", "Preferências..."),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            },
            3: {
                "type": GLib.Variant("s", "separator"),
                "visible": GLib.Variant("b", True),
            },
            4: {
                "label": GLib.Variant("s", "Encerrar o aplicativo"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            },
        }
        if self._ao_exportar:
            itens[5] = {
                "label": GLib.Variant("s", "Exportar Conversa (Markdown)..."),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }
        return itens

    def _handle_menu_call(self, conn, sender, path, iface, method, params, inv):
        menu_items = self._obter_itens_menu()

        if method == "GetLayout":
            ids_exibir = [100, 1, 2]
            if self._ao_exportar:
                ids_exibir.append(5)
            ids_exibir.extend([3, 4])
            children = [
                GLib.Variant("(ia{sv}av)", (item_id, menu_items[item_id], []))
                for item_id in ids_exibir
                if item_id in menu_items
            ]
            root = (0, {"children-display": GLib.Variant("s", "submenu")}, children)
            inv.return_value(GLib.Variant("(u(ia{sv}av))", (self._menu_revision, root)))

        elif method == "GetGroupProperties":
            ids = list(params[0])
            names = set(params[1]) if len(params) > 1 and params[1] else set()
            res = []
            for item_id in ids:
                if item_id in menu_items:
                    props = menu_items[item_id]
                    if names:
                        filtered = {k: v for k, v in props.items() if k in names}
                    else:
                        filtered = props
                    res.append((item_id, filtered))
            inv.return_value(GLib.Variant("(a(ia{sv}))", (res,)))

        elif method == "GetProperty":
            item_id = params[0]
            prop_name = params[1]
            if item_id in menu_items and prop_name in menu_items[item_id]:
                inv.return_value(GLib.Variant("(v)", (menu_items[item_id][prop_name],)))
            else:
                inv.return_value(GLib.Variant("(v)", (GLib.Variant("s", ""),)))

        elif method == "AboutToShow":
            inv.return_value(GLib.Variant("(b)", (False,)))

        elif method == "Event":
            item_id = params[0]
            event_id = params[1]
            if event_id == "clicked":
                if item_id == 1:
                    GLib.idle_add(self._ao_alternar)
                elif item_id == 2:
                    GLib.idle_add(self._ao_preferencias)
                elif item_id == 5 and self._ao_exportar:
                    GLib.idle_add(self._ao_exportar)
                elif item_id == 4:
                    GLib.idle_add(self._ao_sair)
            inv.return_value(None)
        else:
            inv.return_value(None)

    def _handle_menu_get_property(self, conn, sender, path, iface, name):
        props = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", [str(Path.home() / ".local/share/icons")]),
        }
        return props.get(name)

    # ------------------------------------------------------------- Atualizações

    def definir_status(self, texto: str, estado: str = "escutando"):
        self._status_texto = texto
        self._estado = estado
        self._menu_revision += 1

        if self._sni_ativo:
            try:
                self._bus.emit_signal(
                    None,
                    "/StatusNotifierItem",
                    "org.kde.StatusNotifierItem",
                    "NewToolTip",
                    None,
                )
                self._bus.emit_signal(
                    None,
                    "/MenuBar",
                    "com.canonical.dbusmenu",
                    "LayoutUpdated",
                    GLib.Variant("(ui)", (self._menu_revision, 0)),
                )
            except Exception:
                pass

        if self._gtk_status_icon:
            self._gtk_status_icon.set_tooltip_text(f"Acorda, Neo — {texto}")

    def destruir(self):
        """Limpa registros DBus e bandeja ao encerrar a aplicação."""
        if self._sni_ativo and hasattr(self, "_bus") and self._bus:
            try:
                if hasattr(self, "_sni_reg_id") and self._sni_reg_id:
                    self._bus.unregister_object(self._sni_reg_id)
                if hasattr(self, "_menu_reg_id") and self._menu_reg_id:
                    self._bus.unregister_object(self._menu_reg_id)
            except Exception:
                pass
        if self._gtk_status_icon:
            self._gtk_status_icon.set_visible(False)

