"""
API routes for conversation organization (folders, tags, favorites).
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from supervisor_agent.db import crud, schemas
from supervisor_agent.db.database import get_db

router = APIRouter(prefix="/api/v1", tags=["organization"])


# Folder endpoints

@router.post("/folders", response_model=schemas.FolderResponse)
async def create_folder(
    folder: schemas.FolderCreate,
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> schemas.FolderResponse:
    """Create a new folder."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        db_folder = crud.FolderCRUD.create_folder(db, folder, user_id)
        
        # Get conversation count for the folder
        conversation_count = crud.FolderCRUD.get_folder_conversation_count(db, db_folder.id)
        
        folder_response = schemas.FolderResponse.model_validate(db_folder)
        folder_response.conversation_count = conversation_count
        
        return folder_response
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create folder: {str(e)}")


@router.get("/folders", response_model=List[schemas.FolderResponse])
async def get_folders(
    parent_id: Optional[UUID] = Query(None, description="Parent folder ID (omit for root folders)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> List[schemas.FolderResponse]:
    """Get folders, optionally filtered by parent."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        folders = crud.FolderCRUD.get_folders(db, user_id, parent_id, skip, limit)
        
        # Add conversation counts for each folder
        folder_responses = []
        for folder in folders:
            folder_response = schemas.FolderResponse.model_validate(folder)
            folder_response.conversation_count = crud.FolderCRUD.get_folder_conversation_count(db, folder.id)
            folder_responses.append(folder_response)
        
        return folder_responses
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get folders: {str(e)}")


@router.get("/folders/{folder_id}", response_model=schemas.FolderResponse)
async def get_folder(
    folder_id: UUID,
    db: Session = Depends(get_db),
) -> schemas.FolderResponse:
    """Get a specific folder by ID."""
    db_folder = crud.FolderCRUD.get_folder(db, folder_id)
    if not db_folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    conversation_count = crud.FolderCRUD.get_folder_conversation_count(db, folder_id)
    
    folder_response = schemas.FolderResponse.model_validate(db_folder)
    folder_response.conversation_count = conversation_count
    
    return folder_response


@router.put("/folders/{folder_id}", response_model=schemas.FolderResponse)
async def update_folder(
    folder_id: UUID,
    folder_update: schemas.FolderUpdate,
    db: Session = Depends(get_db),
) -> schemas.FolderResponse:
    """Update a folder."""
    db_folder = crud.FolderCRUD.update_folder(db, folder_id, folder_update)
    if not db_folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    conversation_count = crud.FolderCRUD.get_folder_conversation_count(db, folder_id)
    
    folder_response = schemas.FolderResponse.model_validate(db_folder)
    folder_response.conversation_count = conversation_count
    
    return folder_response


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Delete a folder. Conversations and subfolders will be moved to the parent folder."""
    success = crud.FolderCRUD.delete_folder(db, folder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    return {"message": "Folder deleted successfully"}


# Tag endpoints

@router.post("/tags", response_model=schemas.TagResponse)
async def create_tag(
    tag: schemas.TagCreate,
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> schemas.TagResponse:
    """Create a new tag."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        # Check if tag already exists
        existing_tag = crud.TagCRUD.get_tag_by_name(db, tag.name, user_id)
        if existing_tag:
            raise HTTPException(status_code=400, detail="Tag with this name already exists")
        
        db_tag = crud.TagCRUD.create_tag(db, tag, user_id)
        return schemas.TagResponse.model_validate(db_tag)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create tag: {str(e)}")


@router.get("/tags", response_model=List[schemas.TagResponse])
async def get_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> List[schemas.TagResponse]:
    """Get tags ordered by usage count."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        tags = crud.TagCRUD.get_tags(db, user_id, skip, limit)
        return [schemas.TagResponse.model_validate(tag) for tag in tags]
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get tags: {str(e)}")


@router.get("/tags/popular", response_model=List[schemas.TagResponse])
async def get_popular_tags(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> List[schemas.TagResponse]:
    """Get the most popular tags by usage count."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        tags = crud.TagCRUD.get_popular_tags(db, user_id, limit)
        return [schemas.TagResponse.model_validate(tag) for tag in tags]
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get popular tags: {str(e)}")


@router.get("/tags/{tag_id}", response_model=schemas.TagResponse)
async def get_tag(
    tag_id: UUID,
    db: Session = Depends(get_db),
) -> schemas.TagResponse:
    """Get a specific tag by ID."""
    db_tag = crud.TagCRUD.get_tag(db, tag_id)
    if not db_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    return schemas.TagResponse.model_validate(db_tag)


@router.put("/tags/{tag_id}", response_model=schemas.TagResponse)
async def update_tag(
    tag_id: UUID,
    tag_update: schemas.TagUpdate,
    db: Session = Depends(get_db),
) -> schemas.TagResponse:
    """Update a tag."""
    db_tag = crud.TagCRUD.update_tag(db, tag_id, tag_update)
    if not db_tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    return schemas.TagResponse.model_validate(db_tag)


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Delete a tag. It will be removed from all conversations."""
    success = crud.TagCRUD.delete_tag(db, tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    return {"message": "Tag deleted successfully"}


# Favorite endpoints

@router.post("/favorites", response_model=schemas.FavoriteResponse)
async def create_favorite(
    favorite: schemas.FavoriteCreate,
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> schemas.FavoriteResponse:
    """Add a conversation to favorites."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        # Check if conversation exists
        conversation = crud.ChatThreadCRUD.get_thread(db, favorite.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Check if already favorited
        existing_favorite = crud.FavoriteCRUD.get_favorite_by_conversation(
            db, favorite.conversation_id, user_id
        )
        if existing_favorite:
            raise HTTPException(status_code=400, detail="Conversation is already favorited")
        
        db_favorite = crud.FavoriteCRUD.create_favorite(db, favorite, user_id)
        return schemas.FavoriteResponse.model_validate(db_favorite)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create favorite: {str(e)}")


@router.get("/favorites", response_model=List[schemas.FavoriteResponse])
async def get_favorites(
    category: Optional[str] = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> List[schemas.FavoriteResponse]:
    """Get user's favorites, optionally filtered by category."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        favorites = crud.FavoriteCRUD.get_favorites(db, user_id, category, skip, limit)
        return [schemas.FavoriteResponse.model_validate(fav) for fav in favorites]
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get favorites: {str(e)}")


@router.get("/favorites/{favorite_id}", response_model=schemas.FavoriteResponse)
async def get_favorite(
    favorite_id: UUID,
    db: Session = Depends(get_db),
) -> schemas.FavoriteResponse:
    """Get a specific favorite by ID."""
    db_favorite = crud.FavoriteCRUD.get_favorite(db, favorite_id)
    if not db_favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    return schemas.FavoriteResponse.model_validate(db_favorite)


@router.put("/favorites/{favorite_id}", response_model=schemas.FavoriteResponse)
async def update_favorite(
    favorite_id: UUID,
    favorite_update: schemas.FavoriteUpdate,
    db: Session = Depends(get_db),
) -> schemas.FavoriteResponse:
    """Update a favorite."""
    db_favorite = crud.FavoriteCRUD.update_favorite(db, favorite_id, favorite_update)
    if not db_favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    return schemas.FavoriteResponse.model_validate(db_favorite)


@router.delete("/favorites/{favorite_id}")
async def delete_favorite(
    favorite_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Remove a conversation from favorites."""
    success = crud.FavoriteCRUD.delete_favorite(db, favorite_id)
    if not success:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    return {"message": "Favorite removed successfully"}


@router.delete("/favorites/conversation/{conversation_id}")
async def remove_favorite_by_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> dict:
    """Remove a conversation from favorites by conversation ID."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        favorite = crud.FavoriteCRUD.get_favorite_by_conversation(db, conversation_id, user_id)
        if not favorite:
            raise HTTPException(status_code=404, detail="Conversation is not favorited")
        
        crud.FavoriteCRUD.delete_favorite(db, favorite.id)
        return {"message": "Favorite removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to remove favorite: {str(e)}")


# Conversation organization endpoints

@router.put("/conversations/{conversation_id}/organization", response_model=schemas.OrganizedConversationResponse)
async def update_conversation_organization(
    conversation_id: UUID,
    organization_update: schemas.ConversationOrganizationUpdate,
    db: Session = Depends(get_db),
) -> schemas.OrganizedConversationResponse:
    """Update conversation organization (folder, tags, pinning, priority)."""
    try:
        db_conversation = crud.ConversationOrganizationCRUD.update_conversation_organization(
            db, conversation_id, organization_update
        )
        if not db_conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Build organized response with relationships
        organized_response = schemas.OrganizedConversationResponse.model_validate(db_conversation)
        
        # Add folder information
        if db_conversation.folder:
            organized_response.folder = schemas.FolderResponse.model_validate(db_conversation.folder)
            organized_response.folder.conversation_count = 0  # Not computed here for performance
        
        # Add tag information
        organized_response.tags = [
            schemas.TagResponse.model_validate(tag) for tag in db_conversation.tags
        ]
        
        # Check if favorited (requires user auth)
        # TODO: Check actual user favorites when auth is implemented
        organized_response.is_favorited = False
        
        return organized_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update conversation organization: {str(e)}")


@router.post("/conversations/search", response_model=List[schemas.OrganizedConversationResponse])
async def search_conversations(
    filter_request: schemas.ConversationFilterRequest,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> List[schemas.OrganizedConversationResponse]:
    """Search and filter conversations with organization features."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        conversations = crud.ConversationOrganizationCRUD.get_organized_conversations(
            db, filter_request, user_id, skip, limit
        )
        
        # Build organized responses
        organized_responses = []
        for conversation in conversations:
            organized_response = schemas.OrganizedConversationResponse.model_validate(conversation)
            
            # Add folder information
            if conversation.folder:
                organized_response.folder = schemas.FolderResponse.model_validate(conversation.folder)
                organized_response.folder.conversation_count = 0  # Not computed here for performance
            
            # Add tag information
            organized_response.tags = [
                schemas.TagResponse.model_validate(tag) for tag in conversation.tags
            ]
            
            # Check if favorited
            # TODO: Check actual user favorites when auth is implemented
            organized_response.is_favorited = crud.FavoriteCRUD.is_conversation_favorited(
                db, conversation.id, user_id
            )
            
            organized_responses.append(organized_response)
        
        return organized_responses
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to search conversations: {str(e)}")


@router.get("/organization/stats", response_model=schemas.OrganizationStatsResponse)
async def get_organization_stats(
    db: Session = Depends(get_db),
    # TODO: Add user authentication
    # current_user: str = Depends(get_current_user)
) -> schemas.OrganizationStatsResponse:
    """Get organization statistics for the current user."""
    try:
        # TODO: Use actual user ID from auth
        user_id = None  # Replace with current_user when auth is implemented
        
        stats = crud.ConversationOrganizationCRUD.get_organization_stats(db, user_id)
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get organization stats: {str(e)}")


# Bulk operations

@router.post("/conversations/bulk/organize")
async def bulk_organize_conversations(
    conversation_ids: List[UUID],
    organization_update: schemas.ConversationOrganizationUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """Bulk update organization for multiple conversations."""
    try:
        updated_count = 0
        failed_count = 0
        
        for conversation_id in conversation_ids:
            try:
                result = crud.ConversationOrganizationCRUD.update_conversation_organization(
                    db, conversation_id, organization_update
                )
                if result:
                    updated_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
        
        return {
            "message": f"Bulk organization update completed",
            "updated_count": updated_count,
            "failed_count": failed_count,
            "total_count": len(conversation_ids)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to bulk organize conversations: {str(e)}")