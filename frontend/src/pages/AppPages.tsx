import { matchPath, useLocation } from "react-router-dom";
import { PersistentPage } from "../components/PersistentPage";
import { Account } from "./Account";
import { Cleanup } from "./Cleanup";
import { Curate } from "./Curate";
import { Dashboard } from "./Dashboard";
import { Discover } from "./Discover";
import { PlaylistDetail } from "./PlaylistDetail";

export function AppPages() {
  const { pathname } = useLocation();
  const playlistMatch = matchPath("/playlists/:playlistId", pathname);

  return (
    <>
      <PersistentPage active={pathname === "/"} pageKey="dashboard">
        <Dashboard />
      </PersistentPage>
      <PersistentPage active={pathname === "/cleanup"} pageKey="cleanup">
        <Cleanup />
      </PersistentPage>
      <PersistentPage active={pathname === "/curate"} pageKey="curate">
        <Curate />
      </PersistentPage>
      <PersistentPage active={pathname === "/discover"} pageKey="discover">
        <Discover />
      </PersistentPage>
      <PersistentPage active={pathname === "/account"} pageKey="account">
        <Account />
      </PersistentPage>
      {playlistMatch && <PlaylistDetail />}
    </>
  );
}
