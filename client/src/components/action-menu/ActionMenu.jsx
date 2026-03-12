import { useEffect, useRef, useState } from "react";

import "./ActionMenu.css";


function ActionMenu({ actions }) {
    const [isOpen, setIsOpen] = useState(false);
    const menuRef = useRef(null);

    useEffect(() => {
        if (!isOpen) {
            return undefined;
        }

        const handleOutsideClick = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };

        document.addEventListener("mousedown", handleOutsideClick);

        return () => {
            document.removeEventListener("mousedown", handleOutsideClick);
        };
    }, [isOpen]);

    return (
        <div className="action-menu" ref={menuRef}>
            <button
                type="button"
                className="action-menu-trigger"
                onClick={() => setIsOpen((prev) => !prev)}
                aria-expanded={isOpen}
                aria-label="Open actions"
            >
                <img src="/assets/options.svg" alt="" />
            </button>
            {
                isOpen &&
                <div className="action-menu-dropdown">
                    {
                        actions.map((action) => (
                            <button
                                key={action.label}
                                type="button"
                                className={`action-menu-item ${action.variant || ""}`}
                                onClick={() => {
                                    setIsOpen(false);
                                    action.onClick();
                                }}
                            >
                                {action.label}
                            </button>
                        ))
                    }
                </div>
            }
        </div>
    );
}

export default ActionMenu;
