import { mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, expect, it } from "vitest";
import { isHostPresent, recallHosts } from "./recall-hosts.js";

const roots: string[] = [];

afterEach(async () => {
  await Promise.all(
    roots.splice(0).map((root) => rm(root, { recursive: true, force: true })),
  );
});

it("registers Qoder CN against its own home directory", async () => {
  const root = path.join(tmpdir(), `recall-hosts-qoder-${process.pid}-${Date.now()}`);
  roots.push(root);
  const descriptor = (await recallHosts(root, {})).find(
    (host) => host.hostId === "qoder",
  );
  expect(descriptor).toMatchObject({
    hostId: "qoder",
    label: "Qoder CN",
    presencePath: path.join(root, ".qoder-cn"),
    layout: { hostId: "qoder" },
  });
  expect(await isHostPresent(descriptor!)).toBe(false);
  await mkdir(path.join(root, ".qoder-cn"), { recursive: true });
  expect(await isHostPresent(descriptor!)).toBe(true);
});

it("gives every DeepSeek Harness profile a matching unique layout identity", async () => {
  const root = path.join(tmpdir(), `recall-hosts-${process.pid}-${Date.now()}`);
  roots.push(root);
  const dshHome = path.join(root, ".dsh");
  for (const profile of ["web", "headless"]) {
    const directory = path.join(dshHome, "profiles", profile);
    await mkdir(directory, { recursive: true });
    await writeFile(path.join(directory, "cordis.yml"), "plugins: []\n");
  }

  const hosts = (await recallHosts(root, { DSH_HOME: dshHome })).filter(
    (host) => host.hostId.startsWith("deepseek-harness:"),
  );

  expect(hosts.map((host) => host.hostId)).toEqual([
    "deepseek-harness:headless",
    "deepseek-harness:web",
  ]);
  expect(hosts.map((host) => host.layout.hostId)).toEqual(
    hosts.map((host) => host.hostId),
  );
  expect(hosts.map((host) => host.layout.hostLabel)).toEqual(
    hosts.map((host) => host.label),
  );
});
