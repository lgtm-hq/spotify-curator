import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { BackgroundActivityProvider } from "./contexts/BackgroundActivityContext";
import { Layout } from "./components/Layout";
import { AppPages } from "./pages/AppPages";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BackgroundActivityProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="*" element={<AppPages />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </BackgroundActivityProvider>
    </QueryClientProvider>
  );
}
