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

/**
 * The command IDs used by the hierarchy browser plugin.
 */
namespace CommandIDs {
  export const open = 'hierarchy-browser:open';
}

/**
 * Initialization data for the hierarchy-browser extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'hierarchy-browser:plugin',
  description: 'A JupyterLab extension for browsing hierarchies',
  autoStart: true,
  requires: [ILauncher],
  activate: (app: JupyterFrontEnd, launcher: ILauncher) => {
    console.log('JupyterLab extension hierarchy-browser is activated!');

    const { commands } = app;

    // Add the command to open hierarchy browser
    commands.addCommand(CommandIDs.open, {
      label: 'Hierarchy Browser',
      caption: 'Open the Hierarchy Browser',
      execute: () => {
        // Create a new widget
        const widget = new Widget();
        widget.id = 'hierarchy-browser-' + Math.random().toString(36).substr(2, 9);
        widget.title.label = 'Hierarchy Browser';
        widget.title.closable = true;
        widget.title.iconClass = 'jp-MaterialIcon jp-TreeViewIcon';

        // Add Hello World content
        const content = document.createElement('div');
        content.style.cssText = `
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          font-family: var(--jp-ui-font-family);
          background: var(--jp-layout-color1);
          color: var(--jp-ui-font-color1);
        `;
        
        const heading = document.createElement('h1');
        heading.textContent = 'Hello World!';
        heading.style.cssText = `
          color: var(--jp-brand-color1);
          margin-bottom: 16px;
        `;
        
        const message = document.createElement('p');
        message.textContent = 'This is your Hierarchy Browser extension. Ready for development!';
        message.style.cssText = `
          font-size: 16px;
          text-align: center;
          max-width: 400px;
          line-height: 1.5;
        `;

        content.appendChild(heading);
        content.appendChild(message);
        widget.node.appendChild(content);

        // Add the widget to the main area
        app.shell.add(widget, 'main');
      }
    });

    // Add to launcher
    launcher.add({
      command: CommandIDs.open,
      category: 'Other',
      rank: 0
    });
  }
};

export default plugin;
