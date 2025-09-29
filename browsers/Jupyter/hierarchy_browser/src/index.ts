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

/**
 * Type definitions for provider data structures.
 */
interface IProviderInfo {
  RootName?: string;
  icons?: Record<string, string>;
  error?: string;
}

interface IProviderObject {
  id: string;
  title?: string;
  class?: string;
  objects?: number;
  icon?: string;
}

interface IRootObjectsResponse {
  objects?: IProviderObject[];
  error?: string;
}

/**
 * Constants used by the hierarchy browser plugin.
 */
namespace Constants {
  export const EXTENSION_ID = 'hierarchy-browser:plugin';
  export const WIDGET_CLASS = 'jp-HierarchyBrowser';
  export const API_ENDPOINT = 'hierarchy-browser/api';
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
  private async makeRequest<T>(action: string): Promise<T> {
    const url = `${this.serverSettings.baseUrl}${Constants.API_ENDPOINT}?action=${action}`;
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
}

/**
 * Hierarchy browser widget for displaying provider data.
 */
class HierarchyBrowserWidget extends Widget {
  private readonly api: HierarchyBrowserAPI;
  private static nextId = 0;

  constructor() {
    super();
    this.id = `hierarchy-browser-${++HierarchyBrowserWidget.nextId}`;
    this.title.label = 'Hierarchy Browser';
    this.title.closable = true;
    this.title.iconClass = 'jp-MaterialIcon jp-TreeViewIcon';
    this.addClass(Constants.WIDGET_CLASS);

    this.api = new HierarchyBrowserAPI();
    this.initialize();
  }

  /**
   * Initialize the widget content.
   */
  private initialize(): void {
    this.createLayout();
    this.loadProviderData();
  }

  /**
   * Create the widget layout structure.
   */
  private createLayout(): void {
    const container = this.createElement('div', 'jp-HierarchyBrowser-container');
    
    const header = this.createElement('h2', 'jp-HierarchyBrowser-header');
    header.textContent = 'Hierarchy Browser';
    
    const statusDiv = this.createElement('div', 'jp-HierarchyBrowser-status');
    statusDiv.dataset.status = 'loading';
    
    const contentDiv = this.createElement('div', 'jp-HierarchyBrowser-content');

    container.appendChild(header);
    container.appendChild(statusDiv);
    container.appendChild(contentDiv);
    this.node.appendChild(container);
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
   * Load and display provider data.
   */
  private async loadProviderData(): Promise<void> {
    const statusDiv = this.node.querySelector('.jp-HierarchyBrowser-status') as HTMLElement;
    const contentDiv = this.node.querySelector('.jp-HierarchyBrowser-content') as HTMLElement;
    
    if (!statusDiv || !contentDiv) {
      console.error('Widget layout elements not found');
      return;
    }

    this.setLoadingState(statusDiv, 'Connecting to provider at localhost:9100...');

    try {
      const [providerInfo, rootObjects] = await Promise.all([
        this.api.getProviderInfo(),
        this.api.getRootObjects()
      ]);

      if (providerInfo.error) {
        this.setErrorState(statusDiv, `Provider error: ${providerInfo.error}`);
        return;
      }

      if (rootObjects.error) {
        this.setErrorState(statusDiv, `Failed to load objects: ${rootObjects.error}`);
        return;
      }

      this.displaySuccess(statusDiv, providerInfo);
      this.displayRootObjects(contentDiv, rootObjects.objects || []);

    } catch (error) {
      this.setErrorState(statusDiv, `Connection failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Set loading state in the status area.
   */
  private setLoadingState(statusElement: HTMLElement, message: string): void {
    statusElement.dataset.status = 'loading';
    statusElement.innerHTML = `<em>${message}</em>`;
  }

  /**
   * Set error state in the status area.
   */
  private setErrorState(statusElement: HTMLElement, message: string): void {
    statusElement.dataset.status = 'error';
    statusElement.innerHTML = `<span class="jp-HierarchyBrowser-error">${message}</span>`;
  }

  /**
   * Display successful connection information.
   */
  private displaySuccess(statusElement: HTMLElement, info: IProviderInfo): void {
    statusElement.dataset.status = 'success';
    const iconCount = info.icons ? Object.keys(info.icons).length : 0;
    
    statusElement.innerHTML = `
      <div class="jp-HierarchyBrowser-success">
        <strong>Connected to provider!</strong><br>
        <strong>Root Name:</strong> ${info.RootName || 'Unknown'}<br>
        <strong>Icons Available:</strong> ${iconCount}
      </div>
    `;
  }

  /**
   * Display root objects list.
   */
  private displayRootObjects(contentElement: HTMLElement, objects: IProviderObject[]): void {
    if (objects.length === 0) {
      contentElement.innerHTML = '<p>No root objects found.</p>';
      return;
    }

    const objectsList = this.createElement('div', 'jp-HierarchyBrowser-objectsList');
    
    const title = this.createElement('h3', 'jp-HierarchyBrowser-objectsTitle');
    title.textContent = `Root Objects (${objects.length}):`;
    
    const list = this.createElement('ul', 'jp-HierarchyBrowser-objects');
    list.innerHTML = objects.map(obj => 
      `<li class="jp-HierarchyBrowser-object">
        <strong>${this.escapeHtml(obj.title || obj.id)}</strong> - 
        ${this.escapeHtml(obj.class || 'Object')} 
        (${obj.objects || 0} children)
      </li>`
    ).join('');
    
    objectsList.appendChild(title);
    objectsList.appendChild(list);
    contentElement.appendChild(objectsList);
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
