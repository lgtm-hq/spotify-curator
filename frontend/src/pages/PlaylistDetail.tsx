import { matchPath, useLocation } from "react-router-dom";
import { PlaylistDetailView } from "../components/playlists/PlaylistDetailView";

export function PlaylistDetail() {
  const { pathname } = useLocation();
  const match = matchPath({ path: "/playlists/:playlistId", end: true }, pathname);
  const playlistId = match?.params.playlistId;
  if (!playlistId) {
    return <p className="text-red-300">Missing playlist id.</p>;
  }
  return <PlaylistDetailView playlistId={playlistId} />;
}
