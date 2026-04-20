import { useState, useEffect } from "react";
 
export function useLocalStorageState<T>(key: string, fallback: T) {
    const [state, setState] = useState<T>(() => {
        try {
            const raw = localStorage.getItem(key);
            return raw ? (JSON.parse(raw) as T) : fallback;
        } catch {
            return fallback;
        }
    });
 
    useEffect(() => {
        try {
            localStorage.setItem(key, JSON.stringify(state));
        } catch {
            // ignore
        }
    }, [key, state])
 
    return [state, setState] as const;
}
 
 