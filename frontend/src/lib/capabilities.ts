import { useQuery } from "@tanstack/react-query";
import { getCapabilities } from "./api";

export const capabilitiesKey = ["capabilities"] as const;

/** What this installation can do. Polled quickly while the model is downloading. */
export function useCapabilities() {
  return useQuery({
    queryKey: capabilitiesKey,
    queryFn: getCapabilities,
    retry: false,
    refetchInterval: (query) => (query.state.data?.model.state === "downloading" ? 2000 : 30_000),
  });
}
