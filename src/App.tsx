import { Navigate, Route, Routes } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import Dashboard from "./pages/Dashboard";
import GISMap from "./pages/GISMap";
import Dimming from "./pages/Dimming";
import Energy from "./pages/Energy";
import Alarms from "./pages/Alarms";
import LEDManagement from "./pages/LEDManagement";
import EmergencyAlert from "./pages/EmergencyAlert";
import FieldOperations from "./pages/FieldOperations";
import OperationsProvider from "./state/OperationsProvider";

export default function App() {
  return (
    <OperationsProvider>
      <Routes>
        <Route element={<MainLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="gis" element={<GISMap />} />
          <Route path="dimming" element={<Dimming />} />
          <Route path="energy" element={<Energy />} />
          <Route path="alarms" element={<Alarms />} />
          <Route path="led" element={<LEDManagement />} />
          <Route path="emergency" element={<EmergencyAlert />} />
          <Route path="field-operations" element={<FieldOperations />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </OperationsProvider>
  );
}
