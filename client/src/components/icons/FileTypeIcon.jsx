function FileTypeIcon({ kind = "file" }) {
    const renderBadge = () => {
        switch (kind) {
            case "image":
                return <path d="M5.2 13.8 8.4 10.6l2.2 2.2 1.8-1.8 3.4 2.8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" fill="none" />;
            case "video":
                return <path d="M8.2 7.3v5.4l4.4-2.7-4.4-2.7Z" fill="currentColor" />;
            case "audio":
                return <path d="M11.9 5.3v6.1a1.8 1.8 0 1 1-1-1.6V6.5l4.1-.9v4.9a1.8 1.8 0 1 1-1-1.6V4.8l-2.1.5Z" fill="currentColor" />;
            case "pdf":
                return <path d="M6.1 12.8h2.3m-2.3-2.1h2.5m-2.5-2.1H9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />;
            case "doc":
                return <path d="M6 8.4h4.5M6 10.8h6M6 13.2h4.9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />;
            case "sheet":
                return (
                    <>
                        <path d="M6.4 8h7.2M6.4 10.8h7.2M9.2 5.2v8.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                        <path d="M12 5.2v8.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                    </>
                );
            case "slides":
                return (
                    <>
                        <rect x="5.8" y="5.8" width="8.4" height="6.1" rx="1" stroke="currentColor" strokeWidth="1.2" fill="none" />
                        <path d="M8.8 13.4h2.4m-3.8 1.6h5.2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                    </>
                );
            case "text":
                return <path d="M6.3 7.2h7.4M8.4 9.8h3.2m-5.3 2.6h7.4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />;
            case "archive":
                return (
                    <>
                        <path d="M8.1 5.1h3.8M8.1 7.2h3.8M8.1 9.3h3.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                        <path d="M10 11.2v2.6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                    </>
                );
            default:
                return <path d="M6.3 8h7.4M6.3 10.8h7.4M6.3 13.6h5.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />;
        }
    };

    return (
        <svg viewBox="0 0 20 20" aria-hidden="true">
            <path
                d="M6 2.8h5.6l3.4 3.4v8.9a2.1 2.1 0 0 1-2.1 2.1H7.1A2.1 2.1 0 0 1 5 15.1V4.9A2.1 2.1 0 0 1 7.1 2.8Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
                fill="none"
            />
            <path
                d="M11.6 2.8v3.1a.8.8 0 0 0 .8.8h2.6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
            />
            {renderBadge()}
        </svg>
    );
}

export default FileTypeIcon;
