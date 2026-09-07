import { useCallback, useEffect, useRef, useState } from "react";
import { readRoute, routeSearch, mergeRoute } from "./workspace.js";

export default function useWorkspaceRoute() {
  const [route, setRoute] = useState(() => readRoute(window.location.search, localStorage));
  const latest = useRef(route);
  const navigate = useCallback((changes, replace = false) => {
    const next = mergeRoute(latest.current, changes);
    if (routeSearch(next) === window.location.search) return;
    latest.current = next;
    window.history[replace ? "replaceState" : "pushState"](null, "", routeSearch(next));
    setRoute(next);
  }, []);
  useEffect(() => {
    const back = () => {
      const next = readRoute(window.location.search, localStorage);
      latest.current = next;
      setRoute(next);
    };
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []);
  return [route, navigate];
}
