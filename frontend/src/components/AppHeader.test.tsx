import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import AppHeader from "./AppHeader";
import { NAVIGATION_BY_ROLE, ROLE_NAMES } from "../core/appNavigation";

describe("AppHeader", () => {
  it.each(["PATIENT", "DOCTOR", "RECEPTIONIST", "PHARMACIST", "ADMIN"] as const)("renders %s navigation from the shared role configuration", role => {
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
    items.forEach(item => expect(html).toContain(renderToStaticMarkup(<>{item.label}</>)));
    expect(html).toContain("Mở menu điều hướng");
  });
});

describe("receptionist overview menu", () => {
  it("groups the receptionist refund page under overview", () => {
    const items = NAVIGATION_BY_ROLE.RECEPTIONIST;
    const overview = items.find(item => item.id === "profile");
    expect(overview?.children?.map(item => item.id)).toEqual(["refunds"]);

    const html = renderToStaticMarkup(
      <AppHeader
        roleName={ROLE_NAMES.RECEPTIONIST}
        displayName="Lễ tân"
        activeItem="refunds"
        items={items}
        onNavigate={() => undefined}
        onLogout={() => undefined}
      />,
    );
    expect(html).toContain('aria-haspopup="menu"');
    expect(html).toContain('aria-expanded="false"');
  });
});
describe("admin overview menu", () => {
  it("groups admin modules under overview", () => {
    const overview = NAVIGATION_BY_ROLE.ADMIN.find(item => item.id === "profile");
    expect(overview?.children?.map(item => item.id)).toEqual(["refunds", "reviews"]);
    expect(NAVIGATION_BY_ROLE.ADMIN.some(item => item.id === "billing" && item.label === "Tài chính")).toBe(true);
    expect(NAVIGATION_BY_ROLE.ADMIN.some(item => item.id === "patients" && item.label === "Bệnh nhân" )).toBe(true);
  });
});
