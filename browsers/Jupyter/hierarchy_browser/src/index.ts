import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import {
  ILauncher
} from '@jupyterlab/launcher';

import {
  Widget
} from '@lumino/widgets';

import {
  ServerConnection
} from '@jupyterlab/services';

// Import toolbar icons
import groupIcon from '../style/Group.png';
import tableIcon from '../style/Table.png';
import zoomInIcon from '../style/ZoomIn.png';
import zoomOutIcon from '../style/ZoomOut.png';
import detailsIcon from '../style/Details.png';

/**
 * Type definitions for provider data structures.
 */
interface IProviderInfo {
  RootName?: string;
  icons?: { filename: string; data: string }[];
  error?: string;
}

interface IProviderObject {
  id: string;
  title?: string;
  class?: string;
  objects?: number;
  icon?: string;
  contextmenu?: IContextMenuItem[];
  openaction?: IContextMenuItem[];
  [key: string]: any;  // Allow additional properties
}

interface IContextMenuItem {
  title: string;
  action?: string;
  host?: string;
  hostname?: string;
  port?: number;
  command?: string;
}

interface IRootObjectsResponse {
  objects?: IProviderObject[];
  error?: string;
}

interface IObjectsResponse {
  objects?: IProviderObject[];
  error?: string;
}

interface INavStackEntry {
  id: string;
  title: string;
  host?: string;
  port?: string;
  remote_id?: string;
}

/**
 * Constants used by the hierarchy browser plugin.
 */
namespace Constants {
  export const EXTENSION_ID = 'hierarchy-browser:plugin';
  export const WIDGET_CLASS = 'jp-HierarchyBrowser';
  export const API_ENDPOINT = 'hierarchy-browser/api';
  export const ICON_CLASS = 'jp-HierarchyBrowser-icon';
  export const ICON_BOX_PX = 64;
  export const ICON_IMAGE_PX = 48;
}

/**
 * The command IDs used by the hierarchy browser plugin.
 */
namespace CommandIDs {
  export const open = 'hierarchy-browser:open';
}

/**
 * API class for interacting with the hierarchy browser server extension.
 */
class HierarchyBrowserAPI {
  private readonly serverSettings: ServerConnection.ISettings;

  constructor() {
    this.serverSettings = ServerConnection.makeSettings();
  }

  /**
   * Make a generic API request to the hierarchy browser endpoint.
   */
  private async makeRequest<T>(action: string, params?: Record<string, string>): Promise<T> {
    const queryParams = new URLSearchParams({ action, ...params });
    const url = `${this.serverSettings.baseUrl}${Constants.API_ENDPOINT}?${queryParams}`;
    const request = ServerConnection.makeRequest(url, { method: 'GET' }, this.serverSettings);
    
    const response = await request;
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API request failed (${response.status}): ${errorText}`);
    }
    
    return response.json() as Promise<T>;
  }

  /**
   * Get provider information including name and available icons.
   */
  async getProviderInfo(): Promise<IProviderInfo> {
    return this.makeRequest<IProviderInfo>('info');
  }

  /**
   * Get root objects from the provider.
   */
  async getRootObjects(): Promise<IRootObjectsResponse> {
    return this.makeRequest<IRootObjectsResponse>('root');
  }

  /**
   * Get child objects for a specific object ID.
   */
  async getObjects(objectId: string): Promise<IObjectsResponse> {
    return this.makeRequest<IObjectsResponse>('objects', { id: objectId });
  }
}

/**
 * Hierarchy browser widget for displaying provider data.
 * Ported from the PyQt5 browser implementation.
 */
class HierarchyBrowserWidget extends Widget {
  private readonly api: HierarchyBrowserAPI;
  private static nextId = 0;
  
  // State management
  private navStack: INavStackEntry[] = [];
  private currentObjects: IProviderObject[] = [];
  private selectedObject: IProviderObject | null = null;
  private iconStore: Map<string, string> = new Map();
  private rootName: string = 'Root';
  private zoomLevel: number = 1.0;
  private iconMode: boolean = true;  // true = grid, false = table
  
  // DOM elements
  private breadcrumbBar!: HTMLElement;
  private toolbar!: HTMLElement;
  private gridContainer!: HTMLElement;
  private tableContainer!: HTMLElement;
  private detailsPanel!: HTMLElement;
  private contentArea!: HTMLElement;

  constructor() {
    super();
    this.id = `hierarchy-browser-${++HierarchyBrowserWidget.nextId}`;
    this.title.label = 'Hierarchy Browser';
    this.title.closable = true;
    this.title.iconClass = Constants.ICON_CLASS;
    this.addClass(Constants.WIDGET_CLASS);

    this.api = new HierarchyBrowserAPI();
    this.initialize();
  }

  /**
   * Initialize the widget content.
   */
  private async initialize(): Promise<void> {
    console.log('HierarchyBrowser: Starting initialization...');
    try {
      this.createLayout();
      console.log('HierarchyBrowser: Layout created');
      await this.loadProviderInfo();
      console.log('HierarchyBrowser: Provider info loaded');
      await this.loadRoot();
      console.log('HierarchyBrowser: Root objects loaded');
    } catch (error) {
      console.error('HierarchyBrowser: Initialization error:', error);
      this.showError(`Initialization failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Create the complete widget layout structure.
   */
  private createLayout(): void {
    const container = this.createElement('div', 'jp-HierarchyBrowser-container');
    
    // Breadcrumb bar
    this.breadcrumbBar = this.createElement('div', 'jp-HierarchyBrowser-breadcrumb');
    container.appendChild(this.breadcrumbBar);
    
    // Main content area (splitter)
    const mainArea = this.createElement('div', 'jp-HierarchyBrowser-main');
    
    // Left panel (toolbar + grid/table)
    const leftPanel = this.createElement('div', 'jp-HierarchyBrowser-leftPanel');
    
    // Toolbar
    this.toolbar = this.createToolbar();
    leftPanel.appendChild(this.toolbar);
    
    // Content area (holds grid or table)
    this.contentArea = this.createElement('div', 'jp-HierarchyBrowser-contentArea');
    leftPanel.appendChild(this.contentArea);
    
    // Grid view
    this.gridContainer = this.createElement('div', 'jp-HierarchyBrowser-grid');
    this.gridContainer.style.display = 'grid';
    this.contentArea.appendChild(this.gridContainer);
    
    // Table view
    this.tableContainer = this.createElement('table', 'jp-HierarchyBrowser-table');
    this.tableContainer.style.display = 'none';
    this.contentArea.appendChild(this.tableContainer);
    mainArea.appendChild(leftPanel);
    
    // Right panel (details)
    this.detailsPanel = this.createDetailsPanel();
    mainArea.appendChild(this.detailsPanel);
    
    container.appendChild(mainArea);
    this.node.appendChild(container);
    
    this.updateBreadcrumb();
  }

  /**
   * Create the toolbar with action buttons.
   */
  private createToolbar(): HTMLElement {
    const toolbar = this.createElement('div', 'jp-HierarchyBrowser-toolbar');
    
    // Group button
    const groupBtn = this.createToolbarButton('Group', groupIcon, () => this.onGroupAction());
    toolbar.appendChild(groupBtn);
    
    // Table toggle button
    const tableBtn = this.createToolbarButton('Table', tableIcon, () => this.onTableToggle());
    toolbar.appendChild(tableBtn);
    
    // Spacer
    const spacer = this.createElement('div', 'jp-HierarchyBrowser-spacer');
    spacer.style.flex = '1';
    toolbar.appendChild(spacer);
    
    // Zoom out button
    const zoomOutBtn = this.createToolbarButton('Zoom Out', zoomOutIcon, () => this.zoomOut());
    toolbar.appendChild(zoomOutBtn);
    
    // Zoom in button
    const zoomInBtn = this.createToolbarButton('Zoom In', zoomInIcon, () => this.zoomIn());
    toolbar.appendChild(zoomInBtn);
    
    // Details toggle button
    const detailsBtn = this.createToolbarButton('Details', detailsIcon, () => this.onDetailsToggle());
    toolbar.appendChild(detailsBtn);
    
    return toolbar;
  }

  /**
   * Create a toolbar button.
   */
  private createToolbarButton(label: string, iconPath: string, onClick: () => void): HTMLElement {
    const button = this.createElement('button', 'jp-HierarchyBrowser-toolbarButton');
    button.title = label; // Tooltip
    
    // Create icon image
    const icon = document.createElement('img');
    icon.className = 'jp-HierarchyBrowser-toolbarIcon';
    icon.src = iconPath;
    icon.alt = label;
    
    button.appendChild(icon);
    button.addEventListener('click', onClick);
    return button;
  }

  /**
   * Create the details panel.
   */
  private createDetailsPanel(): HTMLElement {
    const panel = this.createElement('div', 'jp-HierarchyBrowser-detailsPanel');
    
    const title = this.createElement('div', 'jp-HierarchyBrowser-detailsTitle');
    title.textContent = 'Details';
    panel.appendChild(title);
    
    const content = this.createElement('div', 'jp-HierarchyBrowser-detailsContent');
    content.innerHTML = '<em>Select an item to see details</em>';
    panel.appendChild(content);
    
    return panel;
  }

  /**
   * Helper method to create DOM elements with classes.
   */
  private createElement(tagName: string, className: string): HTMLElement {
    const element = document.createElement(tagName);
    element.className = className;
    return element;
  }

  /**
   * Load provider information and initialize icons.
   */
  private async loadProviderInfo(): Promise<void> {
    try {
      const info = await this.api.getProviderInfo();
      if (!info.error) {
        this.rootName = info.RootName || 'Root';
        this.loadIcons(info.icons || []);
        this.updateBreadcrumb();
      }
    } catch (error) {
      console.error('Failed to load provider info:', error);
    }
  }

  /**
   * Load and store icons from provider.
   */
  private loadIcons(icons: { filename: string; data: string }[]): void {
    for (const icon of icons) {
      this.iconStore.set(icon.filename, icon.data);
    }
  }

  /**
   * Load root objects from provider.
   */
  private async loadRoot(): Promise<void> {
    try {
      const result = await this.api.getRootObjects();
      if (result.error) {
        this.showError(result.error);
      } else {
        this.currentObjects = result.objects || [];
        this.clearSelection();
        this.populateObjects();
      }
    } catch (error) {
      this.showError(`Connection failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Load children for a specific object ID.
   */
  private async loadChildren(objectId: string): Promise<void> {
    try {
      const result = await this.api.getObjects(objectId);
      if (result.error) {
        this.showError(result.error);
      } else {
        this.currentObjects = result.objects || [];
        this.clearSelection();
        this.populateObjects();
      }
    } catch (error) {
      this.showError(`Failed to load children: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Populate the current view with objects.
   */
  private populateObjects(): void {
    if (this.iconMode) {
      this.populateGridView();
    } else {
      this.populateTableView();
    }
  }

  /**
   * Populate the grid view with object tiles.
   */
  private populateGridView(): void {
    this.gridContainer.innerHTML = '';
    
    for (const obj of this.currentObjects) {
      const tile = this.createObjectTile(obj);
      this.gridContainer.appendChild(tile);
    }
  }

  /**
   * Create an object tile for grid view.
   */
  private createObjectTile(obj: IProviderObject): HTMLElement {
    const tile = this.createElement('div', 'jp-HierarchyBrowser-tile');
    
    // Icon
    const iconBox = this.createElement('div', 'jp-HierarchyBrowser-tileIcon');
    const icon = this.getIconElement(obj.icon, obj.objects || 0);
    iconBox.appendChild(icon);
    tile.appendChild(iconBox);
    
    // Title
    const title = this.createElement('div', 'jp-HierarchyBrowser-tileTitle');
    title.textContent = obj.title || obj.id;
    if ((obj.objects || 0) > 0) {
      title.classList.add('jp-HierarchyBrowser-hasChildren');
    }
    tile.appendChild(title);
    
    // Event handlers
    tile.addEventListener('click', () => this.onObjectClick(obj));
    tile.addEventListener('dblclick', () => this.onObjectActivate(obj));
    
    // Context menu
    if (obj.contextmenu && obj.contextmenu.length > 0) {
      tile.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        this.showContextMenu(obj, e.clientX, e.clientY);
      });
    }
    
    return tile;
  }

  /**
   * Get icon element for an object.
   */
  private getIconElement(iconPath: string | undefined, childCount: number): HTMLElement {
    const img = document.createElement('img');
    img.className = 'jp-HierarchyBrowser-icon';
    
    if (iconPath && this.iconStore.has(iconPath)) {
      img.src = `data:image/png;base64,${this.iconStore.get(iconPath)}`;
    } else {
      // Default icon
      img.src = 'data:image/svg+xml;base64,' + btoa('<svg width=\"48\" height=\"48\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"48\" height=\"48\" fill=\"#ccc\"/></svg>');
    }
    
    // Add badge if object has children
    if (childCount > 0) {
      const container = this.createElement('div', 'jp-HierarchyBrowser-iconContainer');
      container.appendChild(img);
      
      const badge = this.createElement('span', 'jp-HierarchyBrowser-badge');
      badge.textContent = String(childCount);
      container.appendChild(badge);
      
      return container;
    }
    
    return img;
  }

  /**
   * Populate table view.
   */
  private populateTableView(): void {
    this.tableContainer.innerHTML = '';
    
    if (this.currentObjects.length === 0) {
      return;
    }
    
    // Build header from all keys
    const allKeys = new Set<string>();
    for (const obj of this.currentObjects) {
      Object.keys(obj).forEach(k => allKeys.add(k));
    }
    const keys = Array.from(allKeys);
    
    // Create header row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    for (const key of keys) {
      const th = document.createElement('th');
      th.textContent = key;
      headerRow.appendChild(th);
    }
    thead.appendChild(headerRow);
    this.tableContainer.appendChild(thead);
    
    // Create data rows
    const tbody = document.createElement('tbody');
    for (const obj of this.currentObjects) {
      const row = document.createElement('tr');
      row.addEventListener('click', () => this.onObjectClick(obj));
      row.addEventListener('dblclick', () => this.onObjectActivate(obj));
      
      for (const key of keys) {
        const td = document.createElement('td');
        const value = obj[key];
        td.textContent = value !== undefined && value !== null ? String(value) : '';
        row.appendChild(td);
      }
      tbody.appendChild(row);
    }
    this.tableContainer.appendChild(tbody);
  }

  /**
   * Handle object click (selection).
   */
  private onObjectClick(obj: IProviderObject): void {
    this.selectedObject = obj;
    this.updateDetailsPanel(obj);
    
    // Update visual selection
    const tiles = this.gridContainer.querySelectorAll('.jp-HierarchyBrowser-tile');
    tiles.forEach(tile => tile.classList.remove('jp-selected'));
    
    // Find and select the clicked tile
    const clickedTile = Array.from(tiles).find(tile => {
      const titleEl = tile.querySelector('.jp-HierarchyBrowser-tileTitle');
      return titleEl && titleEl.textContent === obj.title;
    });
    if (clickedTile) {
      clickedTile.classList.add('jp-selected');
    }
  }

  /**
   * Handle object activation (double-click or Enter).
   */
  private onObjectActivate(obj: IProviderObject): void {
    const childCount = obj.objects || 0;
    
    // Check for openaction
    if (obj.openaction && obj.openaction.length > 0) {
      this.performOpenAction(obj);
      return;
    }
    
    // Navigate into object if it has children
    if (childCount > 0) {
      this.navStack.push({
        id: obj.id,
        title: obj.title || obj.id,
        remote_id: obj.id
      });
      this.updateBreadcrumb();
      this.loadChildren(obj.id);
    }
  }

  /**
   * Perform an object's openaction.
   */
  private performOpenAction(obj: IProviderObject): void {
    if (!obj.openaction || obj.openaction.length === 0) return;
    
    const action = obj.openaction[0];
    const actionType = (action.action || '').toLowerCase();
    
    if (actionType === 'objectbrowser') {
      // Navigate to a different provider or endpoint
      console.log('ObjectBrowser action not yet fully supported in Jupyter');
    } else {
      console.log('Unsupported openaction:', action);
    }
  }

  /**
   * Update the breadcrumb navigation.
   */
  private updateBreadcrumb(): void {
    this.breadcrumbBar.innerHTML = '';
    
    const parts = [this.rootName, ...this.navStack.map(e => e.title)];
    
    for (let i = 0; i < parts.length; i++) {
      const crumb = this.createElement('span', 'jp-HierarchyBrowser-crumb');
      crumb.textContent = parts[i];
      crumb.addEventListener('click', () => this.onBreadcrumbClick(i));
      
      if (i === 0) {
        crumb.classList.add('jp-HierarchyBrowser-rootCrumb');
      }
      
      this.breadcrumbBar.appendChild(crumb);
      
      if (i < parts.length - 1) {
        const separator = this.createElement('span', 'jp-HierarchyBrowser-crumbSeparator');
        separator.textContent = '›';
        this.breadcrumbBar.appendChild(separator);
      }
    }
  }

  /**
   * Handle breadcrumb click.
   */
  private onBreadcrumbClick(index: number): void {
    if (index === 0) {
      // Navigate to root
      this.navStack = [];
      this.updateBreadcrumb();
      this.loadRoot();
    } else {
      // Navigate to a specific level
      const depth = index;
      this.navStack = this.navStack.slice(0, depth);
      this.updateBreadcrumb();
      
      const target = this.navStack[depth - 1];
      this.loadChildren(target.remote_id || target.id);
    }
  }

  /**
   * Update the details panel with object information.
   */
  private updateDetailsPanel(obj: IProviderObject): void {
    const content = this.detailsPanel.querySelector('.jp-HierarchyBrowser-detailsContent');
    if (!content) return;
    
    let html = `<h3>${this.escapeHtml(obj.title || obj.id)}</h3>`;
    html += `<table class=\"jp-HierarchyBrowser-detailsTable\">`;
    
    for (const [key, value] of Object.entries(obj)) {
      if (key === 'contextmenu' || key === 'openaction') continue;
      
      html += `<tr>`;
      html += `<td class=\"jp-HierarchyBrowser-detailsKey\">${this.escapeHtml(key)}</td>`;
      html += `<td class=\"jp-HierarchyBrowser-detailsValue\">${this.escapeHtml(String(value))}</td>`;
      html += `</tr>`;
    }
    
    html += `</table>`;
    content.innerHTML = html;
  }

  /**
   * Clear selection and details.
   */
  private clearSelection(): void {
    this.selectedObject = null;
    const content = this.detailsPanel.querySelector('.jp-HierarchyBrowser-detailsContent');
    if (content) {
      content.innerHTML = '<em>Select an item to see details</em>';
    }
  }

  /**
   * Show context menu for an object.
   */
  private showContextMenu(obj: IProviderObject, x: number, y: number): void {
    // Simple context menu implementation
    const menu = this.createElement('div', 'jp-HierarchyBrowser-contextMenu');
    menu.style.position = 'fixed';
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    
    for (const item of obj.contextmenu || []) {
      const menuItem = this.createElement('div', 'jp-HierarchyBrowser-contextMenuItem');
      menuItem.textContent = item.title;
      menuItem.addEventListener('click', () => {
        this.executeContextAction(obj, item);
        document.body.removeChild(menu);
      });
      menu.appendChild(menuItem);
    }
    
    document.body.appendChild(menu);
    
    // Close menu on click outside
    const closeMenu = (e: MouseEvent) => {
      if (!menu.contains(e.target as Node)) {
        document.body.removeChild(menu);
        document.removeEventListener('click', closeMenu);
      }
    };
    setTimeout(() => document.addEventListener('click', closeMenu), 100);
  }

  /**
   * Execute a context action.
   */
  private executeContextAction(obj: IProviderObject, action: IContextMenuItem): void {
    console.log('Execute context action:', action.title, 'on', obj.title);
    // Implement action execution based on action type
  }

  /**
   * Handle grouping action.
   */
  private onGroupAction(): void {
    // Collect all properties from current objects
    const props = new Set<string>();
    for (const obj of this.currentObjects) {
      Object.keys(obj).forEach(k => {
        if (!['class', 'id', 'title', 'icon', 'objects', 'contextmenu', 'openaction'].includes(k)) {
          props.add(k);
        }
      });
    }
    
    if (props.size === 0) {
      alert('No properties available for grouping');
      return;
    }
    
    // Show property selection (simple implementation)
    const propArray = Array.from(props);
    const selected = prompt('Enter property name to group by:\\n' + propArray.join(', '));
    
    if (selected && propArray.includes(selected)) {
      this.groupByProperty(selected);
    }
  }

  /**
   * Group objects by a property.
   */
  private groupByProperty(prop: string): void {
    const currentPath = this.getCurrentPath();
    const groupPath = `${currentPath.replace(/\/$/, '')}/<GroupBy:${prop}>`;
    
    this.navStack.push({
      id: currentPath,
      title: `Group by ${prop}`,
      remote_id: groupPath
    });
    this.updateBreadcrumb();
    this.loadChildren(groupPath);
  }

  /**
   * Get current navigation path.
   */
  private getCurrentPath(): string {
    if (this.navStack.length === 0) {
      return '/';
    }
    const last = this.navStack[this.navStack.length - 1];
    return last.remote_id || last.id || '/';
  }

  /**
   * Toggle between grid and table view.
   */
  private onTableToggle(): void {
    this.iconMode = !this.iconMode;
    
    if (this.iconMode) {
      this.gridContainer.style.display = 'grid';
      this.tableContainer.style.display = 'none';
    } else {
      this.gridContainer.style.display = 'none';
      this.tableContainer.style.display = 'table';
    }
    
    this.populateObjects();
  }

  /**
   * Toggle details panel visibility.
   */
  private onDetailsToggle(): void {
    const isVisible = this.detailsPanel.style.display !== 'none';
    this.detailsPanel.style.display = isVisible ? 'none' : 'flex';
  }

  /**
   * Zoom in.
   */
  private zoomIn(): void {
    this.zoomLevel = Math.min(3.0, this.zoomLevel * 1.1);
    this.applyZoom();
  }

  /**
   * Zoom out.
   */
  private zoomOut(): void {
    this.zoomLevel = Math.max(0.5, this.zoomLevel / 1.1);
    this.applyZoom();
  }

  /**
   * Apply zoom level to UI.
   */
  private applyZoom(): void {
    this.node.style.fontSize = `${this.zoomLevel}em`;
  }

  /**
   * Show error message.
   */
  private showError(message: string): void {
    console.error('Hierarchy Browser error:', message);
    this.gridContainer.innerHTML = `<div class=\"jp-HierarchyBrowser-error\">${this.escapeHtml(message)}</div>`;
  }

  /**
   * Escape HTML to prevent XSS.
   */
  private escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

/**
 * Initialization data for the hierarchy-browser extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: Constants.EXTENSION_ID,
  description: 'A JupyterLab extension for browsing hierarchies',
  autoStart: true,
  requires: [ILauncher],
  activate: (app: JupyterFrontEnd, launcher: ILauncher): void => {
    console.log('JupyterLab extension hierarchy-browser is activated!');

    registerCommands(app);
    registerLauncherItems(launcher);
  }
};

/**
 * Register application commands.
 */
function registerCommands(app: JupyterFrontEnd): void {
  const { commands } = app;

  commands.addCommand(CommandIDs.open, {
    label: 'Hierarchy Browser',
    caption: 'Open the Hierarchy Browser',
    iconClass: Constants.ICON_CLASS,
    execute: (): void => {
      const widget = new HierarchyBrowserWidget();
      app.shell.add(widget, 'main');
    }
  });
}

/**
 * Register launcher items.
 */
function registerLauncherItems(launcher: ILauncher): void {
  launcher.add({
    command: CommandIDs.open,
    category: 'Other',
    rank: 0
  });
}

export default plugin;
