import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import QuickActions from './QuickActions.svelte';

describe('QuickActions', () => {
  it('should render create task button', () => {
    const { getByText } = render(QuickActions);
    
    const createButton = getByText(/create task/i);
    expect(createButton).toBeTruthy();
  });
  
  it('should emit createTask event when create button is clicked', async () => {
    const { getByText, component } = render(QuickActions);
    
    const mockHandler = vi.fn();
    component.$on('createTask', mockHandler);
    
    const createButton = getByText(/create task/i);
    await fireEvent.click(createButton);
    
    expect(mockHandler).toHaveBeenCalledTimes(1);
  });
  
  it('should have mobile-optimized buttons', () => {
    const { getByText } = render(QuickActions);
    
    const createButton = getByText(/create task/i);
    expect(createButton.classList.contains('btn-primary')).toBe(true);
  });
  
  it('should render refresh action', () => {
    const { getByText } = render(QuickActions);
    
    const refreshButton = getByText(/refresh/i);
    expect(refreshButton).toBeTruthy();
  });
  
  it('should emit refresh event when refresh button is clicked', async () => {
    const { getByText, component } = render(QuickActions);
    
    const mockHandler = vi.fn();
    component.$on('refresh', mockHandler);
    
    const refreshButton = getByText(/refresh/i);
    await fireEvent.click(refreshButton);
    
    expect(mockHandler).toHaveBeenCalledTimes(1);
  });
  
  it('should be responsive with horizontal scroll on mobile', () => {
    const { container } = render(QuickActions);
    
    const actionsContainer = container.querySelector('.overflow-x-auto');
    expect(actionsContainer).toBeTruthy();
  });
});