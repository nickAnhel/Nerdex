import { useContext, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import "./Moments.css";

import { StoreContext } from "../..";
import AddIcon from "../../components/icons/AddIcon";
import GlobalSearchInput from "../../components/global-search-input/GlobalSearchInput";
import MomentsIcon from "../../components/icons/MomentsIcon";
import MomentsViewer from "../videos/MomentsViewer";


function Moments() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const [searchQuery, setSearchQuery] = useState("");

    return (
        <main className="moments-page">
            <header className="moments-page-header">
                <div className="moments-page-title">
                    <span aria-hidden="true"><MomentsIcon /></span>
                    <div>
                        <h1>Moments</h1>
                        <p>Short vertical videos from the community.</p>
                    </div>
                </div>
                {
                    store.isAuthenticated &&
                    <Link to="/moments/new" className="moments-page-new">
                        <AddIcon />
                        <span>New Moment</span>
                    </Link>
                }
            </header>
            <div className="moments-page-search">
                <GlobalSearchInput
                    value={searchQuery}
                    onChange={setSearchQuery}
                    onSubmit={(query) => navigate(`/search?q=${encodeURIComponent(query)}&type=moment`)}
                    placeholder="Search moments and creators"
                />
            </div>
            <MomentsViewer />
        </main>
    );
}

export default Moments;
