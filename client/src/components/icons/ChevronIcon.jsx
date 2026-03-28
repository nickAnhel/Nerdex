function ChevronIcon({ direction = "right" }) {
    const rotation = {
        right: "0deg",
        left: "180deg",
        up: "-90deg",
        down: "90deg",
    }[direction] || "0deg";

    return (
        <svg viewBox="0 0 20 20" aria-hidden="true" style={{ transform: `rotate(${rotation})` }}>
            <path
                d="m7 4.8 5.4 5.2L7 15.2"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
            />
        </svg>
    );
}

export default ChevronIcon;
