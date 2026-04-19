function IconWrapper({ children, viewBox = "0 0 20 20" }) {
    return (
        <svg viewBox={viewBox} fill="none" aria-hidden="true">
            {children}
        </svg>
    );
}

export function ShareIcon() {
    return (
        <IconWrapper>
            <path d="M7.4 10.2 13.7 6.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M7.4 9.8 13.7 13.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="5.4" cy="10" r="2.2" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="15.1" cy="5.8" r="2.2" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="15.1" cy="14.2" r="2.2" stroke="currentColor" strokeWidth="1.5" />
        </IconWrapper>
    );
}

export function CopyIcon() {
    return (
        <IconWrapper>
            <rect x="6.2" y="5.2" width="8.6" height="9.6" rx="1.4" stroke="currentColor" strokeWidth="1.5" />
            <path d="M4.8 12.8H4A1.8 1.8 0 0 1 2.2 11V4a1.8 1.8 0 0 1 1.8-1.8h7A1.8 1.8 0 0 1 12.8 4v.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </IconWrapper>
    );
}

export function EditIcon() {
    return (
        <IconWrapper>
            <path d="m13.8 4.4 1.8 1.8M6 14.2l-1 2.8 2.8-1 7-7a1.4 1.4 0 0 0 0-2l-.8-.8a1.4 1.4 0 0 0-2 0l-7 7Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </IconWrapper>
    );
}

export function TrashIcon() {
    return (
        <IconWrapper>
            <path d="M4.8 5.6h10.4M8 8.2v5.4M12 8.2v5.4M6.2 5.6l.6 9.2a1.4 1.4 0 0 0 1.4 1.2h3.6a1.4 1.4 0 0 0 1.4-1.2l.6-9.2M7.6 5.4V4a1 1 0 0 1 1-1h2.8a1 1 0 0 1 1 1v1.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </IconWrapper>
    );
}

export function MarkdownIcon() {
    return (
        <IconWrapper>
            <path d="M3.4 14.8V5.2h1.9l2.2 3.1 2.2-3.1h1.9v9.6M12.8 10.4h3.8M14.7 8.5v3.8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </IconWrapper>
    );
}

export function SplitViewIcon() {
    return (
        <IconWrapper>
            <rect x="3" y="4" width="14" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M10 4v12" stroke="currentColor" strokeWidth="1.5" />
        </IconWrapper>
    );
}

export function PreviewIcon() {
    return (
        <IconWrapper>
            <path d="M2.8 10s2.6-4.2 7.2-4.2S17.2 10 17.2 10s-2.6 4.2-7.2 4.2S2.8 10 2.8 10Z" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="10" cy="10" r="2.1" stroke="currentColor" strokeWidth="1.5" />
        </IconWrapper>
    );
}

export default IconWrapper;
