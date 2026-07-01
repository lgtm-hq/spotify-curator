import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Cleanup } from "./pages/Cleanup";
import { Curate } from "./pages/Curate";
import { Dashboard } from "./pages/Dashboard";
import { Discover } from "./pages/Discover";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="cleanup" element={<Cleanup />} />
            <Route path="curate" element={<Curate />} />
            <Route path="discover" element={<Discover />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
