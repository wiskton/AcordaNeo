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
from gi.repository import Gio, GLib, Gtk

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
    ):
        self._ao_alternar = ao_alternar_janela
        self._ao_preferencias = ao_abrir_preferencias
        self._ao_sair = ao_sair
        self._icone_path = icone_path

        self._status_texto = "Diga \"Acorda, Neo\" pra começar"
        self._icone_nome = "audio-input-microphone-symbolic"
        self._sni_ativo = False
        self._gtk_status_icon = None

        self._iniciar_sni()
        if not self._sni_ativo:
            self._iniciar_fallback_gtk()

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
            self._gtk_status_icon.set_from_icon_name(self._icone_nome)
            self._gtk_status_icon.set_tooltip_text(f"Acorda, Neo — {self._status_texto}")
            self._gtk_status_icon.connect("activate", lambda *_a: self._ao_alternar())
            self._gtk_status_icon.connect("popup-menu", self._mostrar_menu_gtk)
            print("[tray] Fallback ativado com Gtk.StatusIcon")
        except Exception as e:
            print(f"[tray] Fallback Gtk.StatusIcon não disponível: {e}")

    def _mostrar_menu_gtk(self, icon, button, activate_time):
        menu = Gtk.Menu()

        item_janela = Gtk.MenuItem(label="Mostrar / Ocultar")
        item_janela.connect("activate", lambda *_a: self._ao_alternar())
        menu.append(item_janela)

        item_pref = Gtk.MenuItem(label="Preferências...")
        item_pref.connect("activate", lambda *_a: self._ao_preferencias())
        menu.append(item_pref)

        menu.append(Gtk.SeparatorMenuItem())

        item_sair = Gtk.MenuItem(label="Sair")
        item_sair.connect("activate", lambda *_a: self._ao_sair())
        menu.append(item_sair)

        menu.show_all()
        menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, activate_time)

    # ----------------------------------------------------------- SNI Handlers

    def _handle_sni_call(self, conn, sender, path, iface, method, params, inv):
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(self._ao_alternar)
        elif method == "ContextMenu":
            # Abre menu de contexto
            pass
        inv.return_value(None)

    def _handle_sni_get_property(self, conn, sender, path, iface, name):
        props = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "acordaneo"),
            "Title": GLib.Variant("s", "Acorda, Neo"),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", self._icone_nome),
            "IconThemePath": GLib.Variant("s", str(self._icone_path.parent) if self._icone_path else ""),
            "Menu": GLib.Variant("o", "/MenuBar"),
            "ItemIsMenu": GLib.Variant("b", False),
            "ToolTip": GLib.Variant(
                "(sa(iiay)ss)",
                (
                    self._icone_nome,
                    [],
                    "Acorda, Neo",
                    self._status_texto,
                ),
            ),
        }
        return props.get(name)

    # ------------------------------------------------------ DBusMenu Handlers

    def _handle_menu_call(self, conn, sender, path, iface, method, params, inv):
        if method == "GetLayout":
            item_toggle = GLib.Variant("(ia{sv}av)", (1, {"label": GLib.Variant("s", "Mostrar / Ocultar")}, []))
            item_pref = GLib.Variant("(ia{sv}av)", (2, {"label": GLib.Variant("s", "Preferências...")}, []))
            item_sep = GLib.Variant("(ia{sv}av)", (3, {"type": GLib.Variant("s", "separator")}, []))
            item_sair = GLib.Variant("(ia{sv}av)", (4, {"label": GLib.Variant("s", "Sair")}, []))

            root = (0, {"children-display": GLib.Variant("s", "submenu")}, [item_toggle, item_pref, item_sep, item_sair])
            inv.return_value(GLib.Variant("(u(ia{sv}av))", (1, root)))
        elif method == "GetGroupProperties":
            inv.return_value(GLib.Variant("(a(ia{sv}))", ([],)))
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
            "IconThemePath": GLib.Variant("as", []),
        }
        return props.get(name)

    # ------------------------------------------------------------- Atualizações

    def definir_status(self, texto: str, estado: str = "escutando"):
        self._status_texto = texto

        if estado == "escutando":
            self._icone_nome = "audio-input-microphone-symbolic"
        elif estado == "pensando":
            self._icone_nome = "system-run-symbolic"
        elif estado == "falando":
            self._icone_nome = "audio-volume-high-symbolic"
        else:
            self._icone_nome = "audio-input-microphone-symbolic"

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
                    "/StatusNotifierItem",
                    "org.kde.StatusNotifierItem",
                    "NewIcon",
                    None,
                )
            except Exception:
                pass

        if self._gtk_status_icon:
            self._gtk_status_icon.set_from_icon_name(self._icone_nome)
            self._gtk_status_icon.set_tooltip_text(f"Acorda, Neo — {texto}")
