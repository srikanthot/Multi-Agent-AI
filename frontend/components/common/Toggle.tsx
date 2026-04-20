"use client";
import { MouseEvent } from 'react';
import './toggle.css';
 
interface ToggleProps {
    id: string;
    checked: boolean;
    onClick: (e: MouseEvent<HTMLButtonElement>) => void;
    label: string;
    disabled: boolean;
}
 
function Toggle({ id, checked, onClick, label, disabled = false }: ToggleProps) {
    return (
        <div className={`toggle-container ${disabled ? 'disabled' : ''}`}>
            {label && <label htmlFor={id} className="toggle-label">{label}</label>}
            <button
                id={id}
                role="switch"
                type="button"
                aria-checked={checked}
                aria-label={label ? undefined : 'Toggle'}
                className={`toggle ${checked ? 'toggle-on' : ''}`}
                onClick={(e) => !disabled && onClick?.(e)}
                disabled={disabled}
            >
                <span className="toggle-thumb" />
            </button>
        </div>);
}
 
export default Toggle;
 
 