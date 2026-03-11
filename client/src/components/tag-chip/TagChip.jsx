import "./TagChip.css";


function TagChip({ slug, onRemove = null }) {
    return (
        <span className="tag-chip">
            <span className="tag-chip-label">#{slug}</span>
            {
                onRemove &&
                <button
                    type="button"
                    className="tag-chip-remove"
                    onClick={() => onRemove(slug)}
                    aria-label={`Remove tag ${slug}`}
                >
                    ×
                </button>
            }
        </span>
    );
}

export default TagChip;
