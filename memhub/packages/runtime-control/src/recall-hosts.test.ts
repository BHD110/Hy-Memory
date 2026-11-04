import { mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, expect, it } from "vitest";
import { recallHosts } from "./recall-hosts.js";

const roots: string[] = [];

afterEach(async () => {
  await Promise.all(
    roots.splice(0).map((root) => rm(root, { recursive: true, force: true })),
  );
});

it("offers Qoder CN with the settings.json and skill Qoder actually reads", async () => {
  const root = path.join(tmpdir(), `recall-hosts-qoder-${process.pid}-${Date.now()}`);
  roots.push(root);
  const qoderDir = path.join(root, ".qoder-cn");
  await mkdir(qoderDir, { recursive: true });

  const qoder = (await recallHosts(root, {})).find(
    (host) => host.hostId === "qoder",
  );

  expect(qoder?.label).toBe("Qoder CN");
  expect(qoder?.presencePath).toBe(qoderDir);
  expect(qoder?.layout.configPath).toBe(path.join(qoderDir, "settings.json"));
  expect(qoder?.layout.skillPath).toBe(
    path.join(qoderDir, "skills", "memhub-recall", "SKILL.md"),
  );
  expect(qoder?.layout.channel).toBe("mcp");
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
