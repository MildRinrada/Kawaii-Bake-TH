"use client";

/**
 * Minimal form submission state, mapped to the backend error contract.
 *
 * Deliberately not a form library: fields stay uncontrolled or in plain
 * component state; this hook owns only what every form repeats 
 * submitting flag, a form-level error message, and per-field errors
 * parsed from `ApiError.details`.
 */

import { useCallback, useState } from "react";

import { ApiError, NetworkError } from "@/lib/api/errors";
import {
  translateFieldErrors,
  translateFormError,
} from "@/lib/forms/friendly-errors";

export interface FormState {
  submitting: boolean;
  formError: string | null;
  fieldErrors: Record<string, string[]>;
}

export function useFormSubmit() {
  const [state, setState] = useState<FormState>({
    submitting: false,
    formError: null,
    fieldErrors: {},
  });

  const submit = useCallback(async (action: () => Promise<void>) => {
    setState({ submitting: true, formError: null, fieldErrors: {} });
    try {
      await action();
      setState({ submitting: false, formError: null, fieldErrors: {} });
      return true;
    } catch (error) {
      if (error instanceof ApiError) {
        setState({
          submitting: false,
          formError: Object.keys(error.details).length
            ? null
            : translateFormError(error.code, error.message),
          fieldErrors: translateFieldErrors(error.fieldErrors()),
        });
      } else if (error instanceof NetworkError) {
        setState({
          submitting: false,
          formError: error.message,
          fieldErrors: {},
        });
      } else {
        setState({
          submitting: false,
          formError: "เกิดข้อผิดพลาดที่ไม่คาดคิด",
          fieldErrors: {},
        });
      }
      return false;
    }
  }, []);

  return { ...state, submit };
}
