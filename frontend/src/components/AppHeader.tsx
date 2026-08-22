import { useEffect, useRef, useState } from "react";
import { Activity, ChevronDown, LogOut, Menu, Settings, X } from "lucide-react";
import type { AppNavItem } from "../core/appNavigation";

type AppHeaderProps = {
  roleName: string;
  displayName: string;
  avatarSrc?: string;
  activeItem: AppNavItem["id"];
  items: AppNavItem[];
  onNavigate: (id: AppNavItem["id"]) => void;
  onOpenAccount?: () => void;
  onLogout: () => void;
};

const FOCUSABLE = "a[href],button:not([disabled]),[tabindex]:not([tabindex='-1'])";

export default function AppHeader(props: AppHeaderProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const drawerRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const userButtonRef = useRef<HTMLButtonElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const initial = props.displayName.trim().slice(0, 1).toLocaleUpperCase("vi") || "D";

  useEffect(() => {
    if (!drawerOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawerRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    function onKeyDown(event: KeyboardEvent) {
      const drawer = drawerRef.current;
      if (event.key === "Escape") {
        setDrawerOpen(false);
        window.requestAnimationFrame(() => menuButtonRef.current?.focus());
        return;
      }
      if (event.key !== "Tab" || !drawer) return;
      const items = Array.from(drawer.querySelectorAll<HTMLElement>(FOCUSABLE));
      const first = items[0];
      const last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [drawerOpen]);

  useEffect(() => {
    if (!userOpen) return;
    window.requestAnimationFrame(() => userMenuRef.current?.querySelector<HTMLElement>("[role='menuitem']")?.focus());
    function close(event: MouseEvent) {
      if (!userMenuRef.current?.contains(event.target as Node)) setUserOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setUserOpen(false);
        window.requestAnimationFrame(() => userButtonRef.current?.focus());
      }
    }
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [userOpen]);

  function navigate(id: AppNavItem["id"]) {
    props.onNavigate(id);
    if (drawerOpen) closeDrawer();
  }

  function closeDrawer() {
    setDrawerOpen(false);
    window.requestAnimationFrame(() => menuButtonRef.current?.focus());
  }

  const navigation = (mobile = false) => (
    <nav className={mobile ? "app-nav app-nav-mobile" : "app-nav"} aria-label={`Điều hướng ${props.roleName}`}>
      {props.items.map(item => {
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            type="button"
            className={props.activeItem === item.id ? "is-active" : ""}
            aria-current={props.activeItem === item.id ? "page" : undefined}
            onClick={() => navigate(item.id)}
          >
            <Icon aria-hidden="true" />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <button type="button" className="app-brand" onClick={() => navigate("profile")} aria-label="Derm Clinic, về trang tổng quan">
          <span className="app-brand-mark" aria-hidden="true"><Activity /></span>
          <span><strong>Derm Clinic</strong><small>{props.roleName}</small></span>
        </button>
        {navigation()}
        <div className="app-header-actions">
          <div className="app-user-menu" ref={userMenuRef}>
            <button ref={userButtonRef} type="button" className="app-user-trigger" aria-expanded={userOpen} aria-haspopup="menu" aria-controls="app-user-popover" onClick={() => setUserOpen(value => !value)}>
              {props.avatarSrc ? <img src={props.avatarSrc} alt="" /> : <span aria-hidden="true">{initial}</span>}
              <span className="app-user-copy"><strong>{props.displayName}</strong><small>{props.roleName}</small></span>
              <ChevronDown aria-hidden="true" />
            </button>
            {userOpen && (
              <div id="app-user-popover" className="app-user-popover" role="menu">
                {props.onOpenAccount && <button type="button" role="menuitem" onClick={() => { setUserOpen(false); props.onOpenAccount?.(); }}><Settings aria-hidden="true" />Tài khoản của tôi</button>}
                <button type="button" role="menuitem" onClick={props.onLogout}><LogOut aria-hidden="true" />Đăng xuất</button>
              </div>
            )}
          </div>
          <button ref={menuButtonRef} type="button" className="app-menu-button" aria-label="Mở menu điều hướng" aria-expanded={drawerOpen} aria-controls="app-navigation-drawer" onClick={() => setDrawerOpen(true)}><Menu aria-hidden="true" /></button>
        </div>
      </div>
      {drawerOpen && (
        <div className="app-drawer-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) closeDrawer(); }}>
          <section id="app-navigation-drawer" ref={drawerRef} className="app-drawer" role="dialog" aria-modal="true" aria-label="Menu điều hướng">
            <div className="app-drawer-heading"><strong>Điều hướng</strong><button type="button" aria-label="Đóng menu" onClick={closeDrawer}><X aria-hidden="true" /></button></div>
            {navigation(true)}
            <div className="app-drawer-account">
              <strong>{props.displayName}</strong><span>{props.roleName}</span>
              {props.onOpenAccount && <button type="button" onClick={() => { setDrawerOpen(false); props.onOpenAccount?.(); }}><Settings aria-hidden="true" />Tài khoản của tôi</button>}
              <button type="button" onClick={props.onLogout}><LogOut aria-hidden="true" />Đăng xuất</button>
            </div>
          </section>
        </div>
      )}
    </header>
  );
}
