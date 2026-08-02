/*
 * electron-builder hook: ad-hoc podpis zabalené .app.
 *
 * Bez platného Developer ID electron-builder podpis přeskočí, jenže na Apple
 * Siliconu se nepodepsaný (resp. přejmenovaný linker-signed) bundle vůbec
 * nespustí – padá hned na startu se SIGTRAP. Ad-hoc podpis to řeší.
 *
 * Podepisovat je nutné zevnitř ven a po jednotlivých kusech; `codesign --deep`
 * u Electronu spolehlivě nefunguje.
 *
 * Pozn.: ad-hoc podpis stačí pro spuštění, ale nenahrazuje notarizaci – na
 * cizím Macu Gatekeeper stejně vyžádá pravý klik → Otevřít.
 */

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

function sign(target) {
  execFileSync("codesign", ["--force", "--sign", "-", "--timestamp=none", target], {
    stdio: "ignore",
  });
}

function isMachO(file) {
  try {
    const fd = fs.openSync(file, "r");
    const buf = Buffer.alloc(4);
    fs.readSync(fd, buf, 0, 4, 0);
    fs.closeSync(fd);
    const magic = buf.readUInt32BE(0);
    // 0xfeedfacf / 0xcffaedfe = 64bit Mach-O, 0xcafebabe = fat binary
    return magic === 0xfeedfacf || magic === 0xcffaedfe || magic === 0xcafebabe;
  } catch {
    return false;
  }
}

function walkBinaries(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isSymbolicLink()) continue;
    if (entry.isDirectory()) {
      // helper .app a .framework podepisujeme jako celek až v druhém kroku
      if (full.endsWith(".app") || full.endsWith(".framework")) continue;
      walkBinaries(full, out);
    } else if (entry.isFile() && isMachO(full)) {
      out.push(full);
    }
  }
  return out;
}

exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== "darwin") return;

  const appPath = path.join(
    context.appOutDir,
    `${context.packager.appInfo.productFilename}.app`
  );
  const frameworks = path.join(appPath, "Contents", "Frameworks");

  // 1) volné Mach-O soubory (dylib, engine binárka, …)
  for (const bin of walkBinaries(appPath)) sign(bin);

  // 2) vnořené bundly – helper aplikace a frameworky
  if (fs.existsSync(frameworks)) {
    for (const name of fs.readdirSync(frameworks)) {
      if (name.endsWith(".app") || name.endsWith(".framework")) {
        sign(path.join(frameworks, name));
      }
    }
  }

  // 3) nakonec celý bundle
  sign(appPath);

  console.log(`  • ad-hoc podepsáno  ${appPath}`);
};
