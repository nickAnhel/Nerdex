import { useSearchParams } from 'react-router-dom';
import "./SearchResults.css"

import UserService from '../../service/UserService';

import UserList from '../../components/user-list/UserList';

import Search from '../../components/search/Search';


function SearchResults() {
    const [searchParams] = useSearchParams();
    const searchScope = searchParams.get("scope");
    const searchQuery = searchParams.get("query");

    return (
        <div id="search-results">
            <Search searchQuery={searchQuery} searchScope={searchScope} />
            {
                searchScope == "people" &&
                <UserList fetchUsers={UserService.searchUsers} filters={{query: searchQuery}} refresh={searchQuery} />
            }
        </div>
    )
}

export default SearchResults;