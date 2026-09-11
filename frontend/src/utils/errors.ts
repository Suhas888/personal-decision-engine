export const extractErrorMessage = (errData: unknown): string => {
  if (!errData) return "An unknown error occurred.";
  
  if (typeof errData === "string") return errData;
  
  // FastAPI 422 Unprocessable Entity
  const asRecord = errData as Record<string, unknown>;
  
  if (Array.isArray(asRecord.detail)) {
    return asRecord.detail.map((e: Record<string, unknown>) => e.msg || JSON.stringify(e)).join(", ");
  }
  
  // General FastAPI HttpException
  if (asRecord.detail && typeof asRecord.detail === "string") {
    return asRecord.detail;
  }

  // Fallback
  if (asRecord.message) return asRecord.message as string;
  
  try {
    return JSON.stringify(errData);
  } catch {
    return "An unknown error occurred.";
  }
};

export const handleApiError = async (res: Response, defaultMessage: string = "Request failed"): Promise<never> => {
  let errData;
  try {
    errData = await res.json();
  } catch {
    errData = { detail: res.statusText || defaultMessage };
  }
  
  throw new Error(extractErrorMessage(errData));
};
