import { useContext } from "react";
import { Link } from "react-router-dom";

import "./Moments.css";

import { StoreContext } from "../..";
import AddIcon from "../../components/icons/AddIcon";
import MomentsIcon from "../../components/icons/MomentsIcon";
import MomentsViewer from "../videos/MomentsViewer";


function Moments() {
    const { store } = useContext(StoreContext);

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
            <MomentsViewer />
        </main>
    );
}

export default Moments;
