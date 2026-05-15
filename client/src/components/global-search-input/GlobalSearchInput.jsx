import { useRef } from "react";

import "./GlobalSearchInput.css";

import CloseIcon from "../icons/CloseIcon";
import SearchIcon from "../icons/SearchIcon";


function GlobalSearchInput({
    value,
    onChange,
    onSubmit,
    placeholder = "Search",
    className = "",
    autoFocus = false,
    disabled = false,
}) {
    const inputRef = useRef(null);

    const submit = () => {
        const nextValue = value.trim();
        if (!nextValue || disabled) {
            return;
        }
        onSubmit(nextValue);
    };

    return (
        <div className={`global-search-input ${className}`.trim()}>
            <div className="global-search-input-field">
                <SearchIcon />
                <input
                    ref={inputRef}
                    type="text"
                    placeholder={placeholder}
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key === "Enter") {
                            event.preventDefault();
                            submit();
                        }
                    }}
                    autoFocus={autoFocus}
                    maxLength={120}
                    disabled={disabled}
                />
                {
                    value &&
                    <button
                        type="button"
                        className="global-search-icon-btn"
                        onClick={() => {
                            onChange("");
                            inputRef.current?.focus();
                        }}
                        aria-label="Clear search"
                    >
                        <CloseIcon />
                    </button>
                }
                <button
                    type="button"
                    className="global-search-submit-btn"
                    onClick={submit}
                    disabled={!value.trim() || disabled}
                >
                    Search
                </button>
            </div>
        </div>
    );
}

export default GlobalSearchInput;
