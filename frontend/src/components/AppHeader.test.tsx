import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import AppHeader from "./AppHeader";
import { NAVIGATION_BY_ROLE, ROLE_NAMES } from "../core/appNavigation";

describe("AppHeader", () => {
  it.each(["PATIENT", "DOCTOR", "RECEPTIONIST", "ADMIN"] as const)("renders %s navigation from the shared role configuration", role => {
    const items = NAVIGATION_BY_ROLE[role];
    const html = renderToStaticMarkup(
      <AppHeader
        roleName={ROLE_NAMES[role]}
        displayName="Nguyễn An"
        activeItem={items[1].id}
        items={items}
        onNavigate={() => undefined}
        onLogout={() => undefined}
      />,
    );

    expect(html).toContain(`Điều hướng ${ROLE_NAMES[role]}`);
    expect(html).toContain("aria-current=\"page\"");
    items.forEach(item => expect(html).toContain(item.label));
    expect(html).toContain("Mở menu điều hướng");
  });
});
