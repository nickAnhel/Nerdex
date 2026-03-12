import ActionMenu from "../action-menu/ActionMenu";


function CommentActionMenu({ onEdit, onDelete }) {
    return (
        <ActionMenu
            actions={[
                {
                    label: "Edit",
                    onClick: onEdit,
                },
                {
                    label: "Delete",
                    variant: "danger",
                    onClick: onDelete,
                },
            ]}
        />
    );
}

export default CommentActionMenu;
