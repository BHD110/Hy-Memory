import { expect, it } from "vitest";
import { connectionHostId, preferenceHasSource } from "./connection-hosts";

it("treats claude and claude-code as the same insertion preference", () => {
  expect(preferenceHasSource(["claude"], "claude-code")).toBe(true);
  expect(preferenceHasSource(["claude-code"], "claude")).toBe(true);
  expect(preferenceHasSource(["cursor"], "workbuddy")).toBe(false);
});

it("maps Qoder CN to its own connection host", () => {
  expect(connectionHostId("qoder")).toBe("qoder");
});
