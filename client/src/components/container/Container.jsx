import { Outlet } from "react-router-dom";
import "./Container.css";


function Container() {
    return (
        <div id="container">
            <Outlet />
        </div>
    )
}

export default Container;