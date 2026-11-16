import { LangProvider } from "./i18n";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AdminApp } from "./admin/AdminApp";
import { DeviceApp } from "./device/DeviceApp";
import { DeviceProvider } from "./device/DeviceContext";

/**
 * Two apps in one bundle:
 *  - /admin/*  back-office for staff (login)
 *  - everything else: the agent PWA on a paired phone (no login)
 */
export function App() {
  return (
    <LangProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/admin/*" element={<AdminApp />} />
        <Route
          path="/pair/:code"
          element={<DeviceProvider><DeviceApp /></DeviceProvider>}
        />
        <Route path="*" element={<DeviceProvider><DeviceApp /></DeviceProvider>} />
      </Routes>
    </BrowserRouter>
    </LangProvider>
  );
}
