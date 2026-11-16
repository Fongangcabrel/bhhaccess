/// <reference types="vitest" />
import basicSsl from "@vitejs/plugin-basic-ssl";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Certificate made by config/pwa/generer-certificat.ps1 (trusted by the phones once its authority
// is installed on them). Without it: a self-signed certificate, fine on the PC only — phones then
// show a « B » icon instead of the logo and the installed app does not open.
const CERTS = path.resolve(__dirname, "../config/pwa/certs");
const trusted = fs.existsSync(path.join(CERTS, "dev-cert.pem")) && fs.existsSync(path.join(CERTS, "dev-key.pem"));

// The certificate names one IP address: warn at start-up when the PC no longer has it.
if (trusted && fs.existsSync(path.join(CERTS, "adresse.txt"))) {
  const certified = fs.readFileSync(path.join(CERTS, "adresse.txt"), "utf8").trim();
  const current = Object.values(os.networkInterfaces()).flat().map((i) => i?.address);
  if (!current.includes(certified)) {
    console.warn(
      `\n⚠  Le certificat est fait pour ${certified}, que ce PC n'a plus.\n` +
        "   Relancez : powershell -ExecutionPolicy Bypass -File config\\pwa\\generer-certificat.ps1\n",
    );
  }
}

/** https://<PC>:5173/bhh-dev-ca.crt: the authority to install on each phone (dev server only). */
function devCertificateAuthority(): Plugin {
  const file = path.join(CERTS, "bhh-dev-ca.crt");
  return {
    name: "bhh-dev-ca",
    configureServer(server) {
      server.middlewares.use("/bhh-dev-ca.crt", (_req, res) => {
        if (!fs.existsSync(file)) {
          res.statusCode = 404;
          res.end("Lancez d'abord config/pwa/generer-certificat.ps1");
          return;
        }
        // This type makes iOS offer « Profil téléchargé » and Android offer the CA install.
        res.setHeader("Content-Type", "application/x-x509-ca-cert");
        res.setHeader("Content-Disposition", 'attachment; filename="bhh-dev-ca.crt"');
        res.end(fs.readFileSync(file));
      });
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    ...(trusted ? [] : [basicSsl()]),
    devCertificateAuthority(),
    VitePWA({
      registerType: "autoUpdate",
      // Serve the manifest and icons on the dev server too: without it the phone has no
      // manifest and draws its own placeholder icon (a "B" on the theme colour).
      devOptions: { enabled: true, type: "module" },
      includeAssets: ["favicon.png", "apple-touch-icon.png"],
      manifest: {
        id: "/",
        name: "BHH Access",
        short_name: "BHH Access",
        description: "Contrôle d'accès par badge QR",
        start_url: "/",
        scope: "/",
        lang: "fr",
        theme_color: "#3D1120",
        background_color: "#3D1120",
        display: "standalone",
        orientation: "portrait",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          // Android crops launcher icons to a circle / squircle: these keep the logo in the safe zone.
          { src: "icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
          { src: "icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      // Only the app shell is cached: scan verdicts must always come live from the server.
      workbox: {
        navigateFallbackDenylist: [/^\/api/],
        // The QR decoder (.wasm, ~1 MB) is cached with the app so the camera starts at once.
        globPatterns: ["**/*.{js,css,html,png,svg,wasm}"],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
    }),
  ],
  // Backend address. Override with VITE_API_TARGET (default: BHHaccess API on port 8001).
  server: {
    proxy: { "/api": process.env.VITE_API_TARGET ?? "http://localhost:8001" },
    https: trusted
      ? { cert: fs.readFileSync(path.join(CERTS, "dev-cert.pem")), key: fs.readFileSync(path.join(CERTS, "dev-key.pem")) }
      : undefined,
  },
  preview: { proxy: { "/api": process.env.VITE_API_TARGET ?? "http://localhost:8001" } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setupTests.ts"] },
});