import {
  disableRuntimeService,
  enableRuntimeService,
  readRuntimeServiceOwner,
  runtimeServiceEnabled,
  setAppRuntimeStartAtLogin,
} from "@one-memory/runtime-control";

export interface LoginPreference {
  supported: boolean;
  enabled: boolean;
  status: string;
}

async function windowsLoginItem() {
  const { app } = await import("electron");
  return {
    app,
    options: {
      name: "MemHub",
      path: process.execPath,
      args: app.isPackaged ? ["--background"] : [app.getAppPath(), "--background"],
    },
  };
}

export async function readLoginPreference(
  dataDir: string,
  platform: NodeJS.Platform,
  supported: boolean,
): Promise<LoginPreference> {
  if (platform === "win32") {
    const { app, options } = await windowsLoginItem();
    const { openAtLogin: enabled } = app.getLoginItemSettings(options);
    return { supported: true, enabled, status: enabled ? "enabled" : "disabled" };
  }
  if (platform !== "darwin" || !supported) {
    return { supported: false, enabled: false, status: "unsupported" };
  }
  try {
    const owner = await readRuntimeServiceOwner(dataDir);
    if (owner?.owner === "cli") {
      return { supported: false, enabled: true, status: "managed-by-cli" };
    }
    if (owner?.owner !== "app") {
      return { supported: false, enabled: false, status: "not-installed" };
    }
    return {
      supported: true,
      enabled: owner.start_at_login && (await runtimeServiceEnabled(dataDir)),
      status:
        owner.start_at_login && (await runtimeServiceEnabled(dataDir))
          ? "enabled"
          : "disabled",
    };
  } catch {
    return { supported: true, enabled: false, status: "unavailable" };
  }
}

export async function setLoginPreference(
  dataDir: string,
  platform: NodeJS.Platform,
  input: unknown,
  supported: boolean,
): Promise<LoginPreference> {
  if (
    !input ||
    typeof input !== "object" ||
    !("openAtLogin" in input) ||
    typeof input.openAtLogin !== "boolean" ||
    !("userConfirmed" in input) ||
    input.userConfirmed !== true
  ) {
    throw Error("login_preference_confirmation_required");
  }
  if (platform === "win32") {
    const { app, options } = await windowsLoginItem();
    app.setLoginItemSettings({ ...options, openAtLogin: input.openAtLogin });
    return readLoginPreference(dataDir, platform, supported);
  }
  if (platform !== "darwin" || !supported) {
    throw Error("login_preference_unsupported");
  }
  await setAppRuntimeStartAtLogin(dataDir, input.openAtLogin);
  if (input.openAtLogin) await enableRuntimeService(dataDir);
  else await disableRuntimeService(dataDir);
  return readLoginPreference(dataDir, platform, supported);
}
