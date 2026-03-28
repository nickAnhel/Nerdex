function VolumeIcon({ muted = false }) {
    return (
        <svg viewBox="0 0 20 20" aria-hidden="true">
            <path
                d="M4.6 11.8H7l3.1 2.6V5.6L7 8.2H4.6a.8.8 0 0 0-.8.8V11a.8.8 0 0 0 .8.8Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
                fill="none"
            />
            {muted ? (
                <path
                    d="M13 7.2 16.2 12.8M16.2 7.2 13 12.8"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                />
            ) : (
                <>
                    <path
                        d="M13.2 8.1a2.7 2.7 0 0 1 0 3.8"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        fill="none"
                    />
                    <path
                        d="M14.9 6.4a5 5 0 0 1 0 7.2"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        fill="none"
                    />
                </>
            )}
        </svg>
    );
}

export default VolumeIcon;
