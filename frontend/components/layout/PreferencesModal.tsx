"use client";
import { useState } from 'react';
import Toggle from "@/components/common/Toggle";
import { MouseEvent, useEffect } from "react";
import { SettingsGearIcon } from "@/components/common/Icons"
import type { Preference } from "@/lib/types";
import { usePreferences } from "@/contexts/preferencesContext";
import "./preferences.css";
 
interface PreferencesProps {
    isOpen: boolean;
    onClose?: () => void;
}
 
function PreferencesModal(props: PreferencesProps) {
    const { isOpen } = props;
    const { preferences, setPreferences } = usePreferences();
    const [shouldRender, setShouldRender] = useState(false);
    const [animating, setAnimating] = useState(false);
 
    useEffect(() => {
        if (isOpen) {
            setShouldRender(true);
            requestAnimationFrame(() => setAnimating(true));
        } else if (shouldRender) {
            setAnimating(false);
        }
    }, [isOpen, preferences]);
 
    const handleAnimationEnd = () => {
        if (!isOpen) {
            setShouldRender(false);
        }
    };
 
    if (!shouldRender) return null;
 
    const handlePreferenceClick = (e: MouseEvent) => {
        const target = e.currentTarget;
        //Note: the toggle button handles the disabled check
        const newPreferences: Preference[] = [];
        preferences.map(p => {
            const value = p.value;
            newPreferences.push(p.key === target.id ? {
                ...p,
                value: p.alternateValue,
                alternateValue: value,
                checked: !p.checked
            } : p);
        });
        setPreferences(() => newPreferences);
    };
 
    return (
        <>
            <div
                className={`preferences ${animating ? 'open' : ''}`}
                onTransitionEnd={handleAnimationEnd}
                aria-label="Preference Settings"
            >
                {/* Header */}
                <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <SettingsGearIcon width={20} height={20} />
                        <h2
                            style={{
                                fontSize: "var(--font-size-lg)",
                                fontWeight: 700,
                            }}
                        >
                            Preferences
                        </h2>
                    </div>
                </div>
 
                {/* Preference Settings */}
                {preferences && preferences.length > 0 && preferences.map((p) => p ?
                    <Toggle
                        key={p.key}
                        id={p.key}
                        onClick={(e: MouseEvent) => handlePreferenceClick(e)}
                        label={p.displayName}
                        checked={p.checked}
                        disabled={false}
                    /> : null
                )}
            </div>
        </>
    );
}
export default PreferencesModal;
 