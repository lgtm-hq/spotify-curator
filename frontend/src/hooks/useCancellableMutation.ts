import {
  useMutation,
  type UseMutationOptions,
  type UseMutationResult,
} from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import { isRequestCancelled } from "../api/client";

export function useCancellableMutation<TData, TVariables = void>(
  mutationFn: (variables: TVariables, signal: AbortSignal) => Promise<TData>,
  options?: Omit<UseMutationOptions<TData, Error, TVariables>, "mutationFn">,
): UseMutationResult<TData, Error, TVariables> & {
  cancel: () => void;
  isRequestCancelled: (error: unknown) => boolean;
} {
  const abortRef = useRef<AbortController | null>(null);

  const mutation = useMutation({
    ...options,
    mutationFn: (variables: TVariables) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      return mutationFn(variables, controller.signal);
    },
  });

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    mutation.reset();
  }, [mutation]);

  return Object.assign(mutation, { cancel, isRequestCancelled });
}

export { isRequestCancelled };
