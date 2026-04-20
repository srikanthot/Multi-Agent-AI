"use client";
 
import { createContext, useContext } from 'react';
import type { Preference } from "@/lib/types";
import { useLocalStorageState } from '../hooks/useLocalStorageState';
 
const availablePreferences: Preference[] = [
    { key: "theme", displayName: "Dark Theme", value: "light", alternateValue: "dark", checked: false } as Preference
];
 
interface PreferencesContextValue {
    preferences: Preference[];
    setPreferences: React.Dispatch<React.SetStateAction<Preference[]>>;
    getPreference: (pref: string) => Preference | undefined;
}
 
const PreferencesContext = createContext<PreferencesContextValue | null>(null);
 
export function PreferencesProvider({ children }: { children: React.ReactNode }) {
    const [preferences, setPreferences] = useLocalStorageState<Preference[]>(
        "preferences",
        availablePreferences
    );
 
    function getPreference(key: string): Preference | undefined {
        const pref = preferences.find(p => p.key === key);
        return pref;
    }
 
    return (
        <PreferencesContext.Provider value={{ preferences, setPreferences, getPreference }}>
            {children}
        </PreferencesContext.Provider>
    );
}
 
export function usePreferences() {
    const ctx = useContext(PreferencesContext);
    if (!ctx) throw new Error("usePreferences must be used inside PreferencesProvider");
    return ctx;
}
 