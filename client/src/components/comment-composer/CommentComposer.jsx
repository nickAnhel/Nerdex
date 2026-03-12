import { useEffect, useRef, useState } from "react";

import "./CommentComposer.css";


const COMMENT_BODY_LIMIT = 2048;


function CommentComposer({
    initialValue = "",
    placeholder,
    submitLabel,
    cancelLabel = "Cancel",
    onSubmit,
    onCancel,
    isSubmitting = false,
    autoFocus = false,
}) {
    const [value, setValue] = useState(initialValue);
    const [error, setError] = useState("");
    const textareaRef = useRef(null);

    useEffect(() => {
        setValue(initialValue);
    }, [initialValue]);

    useEffect(() => {
        if (autoFocus && textareaRef.current) {
            textareaRef.current.focus();
        }
    }, [autoFocus]);

    useEffect(() => {
        const textarea = textareaRef.current;
        if (!textarea) {
            return;
        }

        textarea.style.height = "0px";
        textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
    }, [value]);

    const handleSubmit = async () => {
        const normalizedValue = value.trim();
        if (!normalizedValue) {
            setError("Comment cannot be empty.");
            return;
        }
        if (normalizedValue.length > COMMENT_BODY_LIMIT) {
            setError(`Comment cannot exceed ${COMMENT_BODY_LIMIT} characters.`);
            return;
        }

        setError("");
        await onSubmit(normalizedValue);
        if (!initialValue) {
            setValue("");
        }
    };

    return (
        <div className="comment-composer">
            <textarea
                ref={textareaRef}
                value={value}
                maxLength={COMMENT_BODY_LIMIT}
                placeholder={placeholder}
                onChange={(event) => {
                    setValue(event.target.value);
                    if (error) {
                        setError("");
                    }
                }}
                onKeyDown={(event) => {
                    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                        event.preventDefault();
                        void handleSubmit();
                    }
                }}
                rows={1}
                disabled={isSubmitting}
            />
            <div className="comment-composer-footer">
                <span className="comment-composer-meta">
                    {value.trim().length}/{COMMENT_BODY_LIMIT}
                </span>
                <div className="comment-composer-actions">
                    {
                        onCancel &&
                        <button
                            type="button"
                            className="secondary"
                            onClick={onCancel}
                            disabled={isSubmitting}
                        >
                            {cancelLabel}
                        </button>
                    }
                    <button
                        type="button"
                        onClick={() => { void handleSubmit(); }}
                        disabled={isSubmitting}
                    >
                        {isSubmitting ? "Saving..." : submitLabel}
                    </button>
                </div>
            </div>
            {
                error &&
                <p className="comment-composer-error">{error}</p>
            }
        </div>
    );
}

export default CommentComposer;
