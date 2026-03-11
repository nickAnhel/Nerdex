import { useEffect, useState } from "react";

import "./TagInput.css";

import TagService from "../../service/TagService";
import {
    dedupeTags,
    getTagValidationError,
    normalizeTagValue,
    TAG_FORMAT_HINT,
} from "../../utils/tags";
import TagChip from "../tag-chip/TagChip";


function TagInput({
    tags,
    onChange,
    onInputStateChange,
}) {
    const [inputValue, setInputValue] = useState("");
    const [inputError, setInputError] = useState("");
    const [suggestions, setSuggestions] = useState([]);

    useEffect(() => {
        setInputValue("");
        setInputError("");
        setSuggestions([]);
        if (onInputStateChange) {
            onInputStateChange({
                value: "",
                normalizedValue: "",
                error: "",
            });
        }
    }, [tags, onInputStateChange]);

    useEffect(() => {
        const normalizedValue = normalizeTagValue(inputValue);
        if (!normalizedValue || inputError) {
            setSuggestions([]);
            return;
        }

        let isCancelled = false;
        const timerId = setTimeout(async () => {
            try {
                const res = await TagService.getSuggestions(normalizedValue);
                if (!isCancelled) {
                    setSuggestions(
                        res.data.filter((tag) => !tags.includes(tag.slug))
                    );
                }
            } catch (e) {
                if (!isCancelled) {
                    setSuggestions([]);
                }
            }
        }, 250);

        return () => {
            isCancelled = true;
            clearTimeout(timerId);
        };
    }, [inputValue, inputError, tags]);

    const updateInputState = (nextValue, nextError) => {
        if (onInputStateChange) {
            onInputStateChange({
                value: nextValue,
                normalizedValue: normalizeTagValue(nextValue),
                error: nextError,
            });
        }
    };

    const handleInputChange = (event) => {
        const nextValue = event.target.value;
        const nextError = getTagValidationError(nextValue);

        setInputValue(nextValue);
        setInputError(nextError);
        updateInputState(nextValue, nextError);
    };

    const addTag = (rawValue) => {
        const normalizedValue = normalizeTagValue(rawValue);
        const nextError = getTagValidationError(rawValue);

        if (!normalizedValue) {
            setInputValue("");
            setInputError("");
            updateInputState("", "");
            return false;
        }

        if (nextError) {
            setInputError(nextError);
            updateInputState(rawValue, nextError);
            return false;
        }

        onChange(dedupeTags([...tags, normalizedValue]));
        setInputValue("");
        setInputError("");
        setSuggestions([]);
        updateInputState("", "");
        return true;
    };

    const handleKeyDown = (event) => {
        if (event.key !== "Enter") {
            return;
        }

        event.preventDefault();
        addTag(inputValue);
    };

    return (
        <div className="tag-input">
            <div className="tag-input-header">
                <span>Tags</span>
                <p>{TAG_FORMAT_HINT}</p>
            </div>

            <div className="tag-input-field">
                <div className="tag-input-chips">
                    {
                        tags.map((tag) => (
                            <TagChip
                                key={tag}
                                slug={tag}
                                onRemove={(slug) => onChange(tags.filter((item) => item !== slug))}
                            />
                        ))
                    }
                </div>

                <input
                    type="text"
                    value={inputValue}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder="Type tag and press Enter"
                    maxLength={64}
                />
            </div>

            {inputError && <div className="tag-input-error">{inputError}</div>}

            {
                !inputError && suggestions.length > 0 &&
                <div className="tag-input-suggestions">
                    {
                        suggestions.map((tag) => (
                            <button
                                key={tag.tag_id}
                                type="button"
                                onClick={() => addTag(tag.slug)}
                            >
                                #{tag.slug}
                            </button>
                        ))
                    }
                </div>
            }
        </div>
    );
}

export default TagInput;
