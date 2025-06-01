import { useState } from "react"
import { useNavigate } from "react-router-dom";

import "./Search.css"


function Search({ searchScope, searchQuery }) {
    const navigate = useNavigate();

    const [query, setQuery] = useState(searchQuery || "");

    const handlePressEnter = (e) => {
        if (e.key == "Enter" && query) {
            navigate(`/search?scope=${searchScope}&query=${query}`)
        }
    }

    const handleSearch = () => {
        if (query) {
            navigate(`/search?scope=${searchScope}&query=${query}`)
        }
    }

    const handleClear = () => {
        setQuery("");
        document.getElementById("search-input").focus();
    }

    return (
        <div id="search">
            <div className="search-bar">
                <input
                    id="search-input"
                    type="text"
                    placeholder="Search"
                    value={query}
                    maxLength={50}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handlePressEnter}
                />
                <div className="search-actions">
                    <button
                        className={query ? "show search-btn" : "search-btn hidden"}
                        onClick={handleClear}
                        disabled={!query}
                    >
                        <img
                            className="close"
                            src="assets/clear.svg"
                            alt="Clear"
                        />
                    </button>
                    <button
                        className="search-btn"
                        disabled={!query}
                    >
                        <img
                            src="assets/search.svg"
                            alt="Search"
                            onClick={handleSearch}
                        />
                    </button>
                </div>
            </div>
        </div>
    )
}

export default Search