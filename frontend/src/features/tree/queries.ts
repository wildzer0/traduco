import { useQuery } from "@tanstack/react-query";
import { getSkeletonCheck, getTree, listProjects } from "../../lib/api";

export const keys = {
  projects: ["projects"] as const,
  tree: (id: string) => ["tree", id] as const,
  skeleton: (id: string) => ["skeleton", id] as const,
  file: (id: string, path: string) => ["file", id, path] as const,
};

export const useProjects = () => useQuery({ queryKey: keys.projects, queryFn: listProjects });

export const useTree = (projectId: string) =>
  useQuery({
    queryKey: keys.tree(projectId),
    queryFn: async () => (await getTree(projectId)).nodes,
  });

/** Conformity with the project skeleton; `data` is `null` for projects without one. */
export const useSkeleton = (projectId: string) =>
  useQuery({
    queryKey: keys.skeleton(projectId),
    queryFn: () => getSkeletonCheck(projectId),
    retry: false,
  });
