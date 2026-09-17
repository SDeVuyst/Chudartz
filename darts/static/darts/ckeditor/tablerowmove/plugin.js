(function () {
  'use strict';

  function getSelectedRow(editor) {
    var selection = editor.getSelection();
    if (!selection) {
      return null;
    }
    var element = selection.getStartElement();
    if (!element) {
      return null;
    }
    var cell = element.getAscendant({ td: 1, th: 1 }, true);
    if (!cell) {
      return null;
    }
    var row = cell.getAscendant('tr', true);
    if (!row) {
      return null;
    }
    var parent = row.getParent();
    if (!parent || parent.getName() !== 'tbody') {
      return null;
    }
    return row;
  }

  // Skip whitespace/text nodes between <tr> elements (getNext/getPrevious do not).
  function getSiblingRow(row, direction) {
    if (!row || !row.$) {
      return null;
    }
    var el =
      direction < 0 ? row.$.previousElementSibling : row.$.nextElementSibling;
    while (el) {
      if (el.nodeName && el.nodeName.toLowerCase() === 'tr') {
        return new CKEDITOR.dom.element(el);
      }
      el = direction < 0 ? el.previousElementSibling : el.nextElementSibling;
    }
    return null;
  }

  function canMove(row, direction) {
    return !!getSiblingRow(row, direction);
  }

  function firstCell(row) {
    if (!row) {
      return null;
    }
    return row.getFirst(function (node) {
      return (
        node.type === CKEDITOR.NODE_ELEMENT &&
        (node.getName() === 'td' || node.getName() === 'th')
      );
    });
  }

  function refreshMoveCommands(editor) {
    var path = editor.elementPath();
    var up = editor.getCommand('rowMoveUp');
    var down = editor.getCommand('rowMoveDown');
    if (up && up.refresh) {
      up.refresh(editor, path);
    }
    if (down && down.refresh) {
      down.refresh(editor, path);
    }
  }

  function moveRow(editor, direction) {
    var row = getSelectedRow(editor);
    var sibling = getSiblingRow(row, direction);
    if (!row || !sibling || !row.$ || !sibling.$ || !row.$.parentNode) {
      return;
    }

    editor.fire('saveSnapshot');

    // Native DOM move — keeps cell inline styles / classes intact.
    if (direction < 0) {
      row.$.parentNode.insertBefore(row.$, sibling.$);
    } else if (sibling.$.nextSibling) {
      row.$.parentNode.insertBefore(row.$, sibling.$.nextSibling);
    } else {
      row.$.parentNode.appendChild(row.$);
    }

    // Podium colors follow row position via CSS nth-child; no style rewrite.

    var cell = firstCell(row);
    if (cell) {
      editor.getSelection().selectElement(cell);
    }
    refreshMoveCommands(editor);

    editor.fire('saveSnapshot');
    editor.fire('change');
  }

  function commandState(editor, direction) {
    return canMove(getSelectedRow(editor), direction)
      ? CKEDITOR.TRISTATE_OFF
      : CKEDITOR.TRISTATE_DISABLED;
  }

  CKEDITOR.plugins.add('tablerowmove', {
    // menu/contextmenu are already in the CKEditor build — do not list them in
    // extraPlugins (re-loading them can break editor init / contentsStyle).
    requires: 'table,tabletools',
    icons: 'rowmoveup,rowmovedown',
    hidpi: false,
    init: function (editor) {
      editor.addCommand('rowMoveUp', {
        contextSensitive: true,
        requiredContent: 'table',
        exec: function (ed) {
          moveRow(ed, -1);
        },
        refresh: function (ed) {
          this.setState(commandState(ed, -1));
        },
      });

      editor.addCommand('rowMoveDown', {
        contextSensitive: true,
        requiredContent: 'table',
        exec: function (ed) {
          moveRow(ed, 1);
        },
        refresh: function (ed) {
          this.setState(commandState(ed, 1));
        },
      });

      if (editor.ui.addButton) {
        editor.ui.addButton('RowMoveUp', {
          label: 'Rij omhoog',
          command: 'rowMoveUp',
          toolbar: 'table,20',
          icon: 'rowmoveup',
        });
        editor.ui.addButton('RowMoveDown', {
          label: 'Rij omlaag',
          command: 'rowMoveDown',
          toolbar: 'table,30',
          icon: 'rowmovedown',
        });
      }

      if (editor.addMenuItems) {
        editor.addMenuGroup('tablerowmove', 45);
        editor.addMenuItems({
          tableRowMoveUp: {
            label: 'Rij omhoog',
            command: 'rowMoveUp',
            group: 'tablerowmove',
            order: 1,
            icon: 'rowmoveup',
          },
          tableRowMoveDown: {
            label: 'Rij omlaag',
            command: 'rowMoveDown',
            group: 'tablerowmove',
            order: 2,
            icon: 'rowmovedown',
          },
        });
      }

      if (editor.contextMenu) {
        editor.contextMenu.addListener(function () {
          var row = getSelectedRow(editor);
          if (!row) {
            return null;
          }
          // Always expose both entries when inside a body row. CKEditor hides
          // TRISTATE_DISABLED items entirely, which made "omlaag" disappear.
          return {
            tableRowMoveUp: CKEDITOR.TRISTATE_OFF,
            tableRowMoveDown: CKEDITOR.TRISTATE_OFF,
          };
        });
      }

      editor.on('selectionChange', function () {
        refreshMoveCommands(editor);
      });
    },
  });
})();
