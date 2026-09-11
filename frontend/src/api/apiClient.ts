import { API_BASE_URL } from "./config";

let accessToken: string | null = null;
let isRefreshing = false;
let refreshSubscribers: ((token: string | null) => void)[] = [];

export const setAccessToken = (token: string | null) => {
    accessToken = token;
};

export const getAccessToken = () => accessToken;

const onRefreshed = (token: string | null) => {
    refreshSubscribers.forEach((callback) => callback(token));
    refreshSubscribers = [];
};

const addRefreshSubscriber = (callback: (token: string | null) => void) => {
    refreshSubscribers.push(callback);
};

export const authenticatedFetch = async (
    url: string,
    options: RequestInit = {}
): Promise<Response> => {
    const headers = new Headers(options.headers);
    if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
    }

    const config = {
        ...options,
        headers,
    };

    const response = await fetch(url, config);

    if (response.status === 401) {
        if (!isRefreshing) {
            isRefreshing = true;
            try {
                const refreshResponse = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
                    method: "POST",
                    credentials: "include", // Essential for HttpOnly refresh cookie
                });

                if (refreshResponse.ok) {
                    const data = await refreshResponse.json();
                    setAccessToken(data.access_token);
                    onRefreshed(data.access_token);
                } else {
                    setAccessToken(null);
                    onRefreshed(null);
                    if (typeof window !== "undefined") {
                        window.dispatchEvent(new Event("auth-logout"));
                    }
                }
            } catch {
                setAccessToken(null);
                onRefreshed(null);
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new Event("auth-logout"));
                }
            } finally {
                isRefreshing = false;
            }
        }

        return new Promise((resolve) => {
            addRefreshSubscriber((token) => {
                if (token) {
                    headers.set("Authorization", `Bearer ${token}`);
                    resolve(fetch(url, { ...options, headers }));
                } else {
                    resolve(response);
                }
            });
        });
    }

    return response;
};
