import api from "../http";


function buildActivityParams(params = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value === null || value === undefined || value === "" || value === "all") {
            return;
        }
        if (Array.isArray(value)) {
            value.forEach((item) => searchParams.append(key, item));
            return;
        }
        searchParams.append(key, value);
    });
    return searchParams;
}


export default class ActivityService {
    static async getActivity(params) {
        return api.get("/activity", { params: buildActivityParams(params) });
    }
}
