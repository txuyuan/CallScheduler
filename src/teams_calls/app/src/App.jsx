import React, { useState, useMemo, useRef, useEffect } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { AllEnterpriseModule, ModuleRegistry, themeBalham } from 'ag-grid-enterprise';

ModuleRegistry.registerModules([AllEnterpriseModule]);

// Helper function to generate an array of date strings between start and end
const getDatesBetween = (startStr, endStr) => {
  const dates = [];
  let currentDate = new Date(startStr);
  const endDate = new Date(endStr);

  while (currentDate <= endDate) {
    dates.push(currentDate.toISOString().split('T')[0]); // Format: YYYY-MM-DD
    currentDate.setDate(currentDate.getDate() + 1);
  }
  return dates;
};

// Helper to check if a date string is Saturday or Sunday
const isWeekend = (dateStr) => {
  const d = new Date(dateStr);
  const day = d.getDay();
  return day === 0 || day === 6; // 0 = Sunday, 6 = Saturday
};

export default function DynamicRosterGrid() {
  const [topGridApi, setTopGridApi] = useState(null);
  const [middleGridApi, setMiddleGridApi] = useState(null);
  const [bottomGridApi, setBottomGridApi] = useState(null);

  // Date Range State (Defaults to a 7-day window)
  const [startDate, setStartDate] = useState('2026-09-01');
  const [endDate, setEndDate] = useState('2026-09-30');

  // Compute active date array dynamically
  const dateColumns = useMemo(() => getDatesBetween(startDate, endDate), [startDate, endDate]);

  const [pinColWidth, setPinColWidth] = useState(100);
  const [colWidth, setColWidth] = useState(120);
  const defaultColDef = useMemo(() => {
    return {
      suppressHeaderMenuButton: true, // Hides the 3-dot button on every column header
    };
  }, []);

  // Roster View Mode State: 'both', 'teams', or 'calls'
  const [rosterViewMode, setRosterViewMode] = useState('both');

  // --- Initial Team Requirements Data ---
  const [teamRowData, setTeamRowData] = useState([
    { teamName: 'Team A' },
    { teamName: 'Team B' },
    { teamName: 'Team C' },
    { teamName: 'Team D' },
  ]);

  // --- Initial Call Requirements Data ---
  const [callRowData, setCallRowData] = useState([
    { callName: "Call" }
  ]);

  // Dynamically extract team names from top table to feed bottom dropdown
  const availableTeams = useMemo(() => {
    return teamRowData.map(row => row.teamName).filter(Boolean);
  }, [teamRowData]);

  // --- Separated Personnel Roster Data Structures ---
  const [rosterTeamRowData, setRosterTeamRowData] = useState([
    { name: 'Person 1' },
    { name: 'Person 2' },
    { name: 'Person 3' },
    { name: 'Person 4' },
  ]);

  const [rosterCallRowData, setRosterCallRowData] = useState([
    { name: 'Person 1' },
    { name: 'Person 2' },
    { name: 'Person 3' },
    { name: 'Person 4' },
  ]);

  // Combine the two separate states into a unified dataset for the grid UI
  const rosterGridRowData = useMemo(() => {
    return rosterTeamRowData.map((teamRow, index) => {
      const callRow = rosterCallRowData[index] || { name: teamRow.name };
      const merged = { name: teamRow.name };
      
      dateColumns.forEach(date => {
        const callVal = callRow[date];
        merged[date] = {
          team: teamRow[date] || '',
          // Explicitly check for null/undefined so boolean `false` is preserved!
          call: callVal !== undefined && callVal !== null ? callVal : ''
        };
      });
      return merged;
    });
  }, [rosterTeamRowData, rosterCallRowData, dateColumns]);

  const teamWrapperRef = useRef(null);
  const callWrapperRef = useRef(null);
  const rosterWrapperRef = useRef(null);

  const calcDefaultHeight = ((rowCount, headers=1) => {
    return (headers * 33) + (rowCount * 29) + 18;
  });

  // Automatically recalculate roster height when view mode or row count changes
  useEffect(() => {
    if (rosterWrapperRef.current) {
      const rowCount = bottomGridApi ? bottomGridApi.getDisplayedRowCount() : rosterTeamRowData.length;
      const headers = rosterViewMode === 'both' ? 2 : 1;
      rosterWrapperRef.current.style.height = `${calcDefaultHeight(rowCount, headers)}px`;
    }
  }, [rosterViewMode, bottomGridApi, rosterTeamRowData.length]);

  const isResizingRef = useRef(false);

  const handleColumnResized = (params) => {
    if (isResizingRef.current) return;
    
    // Only sync once the user finishes dragging the column edge
    if (!params.finished) return;

    const resizedCol = params.column;
    const affectedCols = params.columns; // Contains child columns if a group header was resized
    const isPinned = resizedCol ? resizedCol.isPinned() : false;
    
    isResizingRef.current = true;

    // Get all active grid instances
    const allGrids = [topGridApi, bottomGridApi, middleGridApi].filter(Boolean);

    if (isPinned) {
      if (!resizedCol) {
        isResizingRef.current = false;
        return;
      }
      const newWidth = resizedCol.getActualWidth();
      setPinColWidth(newWidth);
      const sourceGrid = allGrids.find(api => api.getColumns().includes(resizedCol));
      if (sourceGrid) {
        const sourcePinnedCols = sourceGrid.getColumns().filter(col => col.isPinned());
        const pinnedIndex = sourcePinnedCols.indexOf(resizedCol);

        allGrids.forEach(gridApi => {
          const targetPinnedCols = gridApi.getColumns().filter(col => col.isPinned());
          const targetCol = targetPinnedCols[pinnedIndex];
          
          if (targetCol) {
            gridApi.applyColumnState({
              state: [{ colId: targetCol.getColId(), width: newWidth }]
            });
          }
        });
      }
    } else {
      // Find the source grid using either the single resized column or the affected columns group
      const sourceGrid = allGrids.find(api => {
        const apiCols = api.getColumns();
        if (resizedCol && apiCols.includes(resizedCol)) return true;
        if (affectedCols && affectedCols.some(col => apiCols.includes(col))) return true;
        return false;
      });

      const isRosterBoth = (sourceGrid === bottomGridApi && rosterViewMode === 'both');
      const targetColToMeasure = resizedCol || (affectedCols && affectedCols[0]);

      let newColWidth = colWidth;

      if (isRosterBoth && affectedCols && affectedCols.length === 2) {
        // Group header was resized in 'both' mode: sum the widths of the two children (Team + Call)
        newColWidth = affectedCols.reduce((sum, col) => sum + col.getActualWidth(), 0);
      } else if (isRosterBoth && targetColToMeasure) {
        // A single sub-column was dragged directly in 'both' mode: double it to get full master width
        newColWidth = targetColToMeasure.getActualWidth() * 2;
      } else if (targetColToMeasure) {
        // Normal single-column table (Top/Middle or Roster in single mode)
        newColWidth = targetColToMeasure.getActualWidth();
      }

      setColWidth(newColWidth);

      // Synchronize width across all active grids
      allGrids.forEach(gridApi => {
        const allCols = gridApi.getColumns();
        const unpinnedCols = allCols.filter(col => !col.isPinned());

        const targetIsRosterBoth = (gridApi === bottomGridApi && rosterViewMode === 'both');

        if (targetIsRosterBoth) {
          // Bottom grid in 'both' mode splits the master width in half for each sub-column
          const halfWidth = Math.floor(newColWidth / 2);
          gridApi.applyColumnState({
            state: unpinnedCols.map(col => ({
              colId: col.getColId(),
              width: halfWidth
            }))
          });
        } else {
          // Top, middle, and single-mode bottom grids receive the full master column width
          const dateColIds = unpinnedCols.map(col => col.getColId());
          gridApi.applyColumnState({
            state: dateColIds.map(id => ({
              colId: id,
              width: newColWidth
            }))
          });
        }
      });
    }

    isResizingRef.current = false;
  };

  // --- Dynamically Build Team Column Definitions ---
  const teamColumnDefs = useMemo(() => {
    const baseCols = [{ field: 'teamName', headerName: 'Team', pinned: 'left', width: pinColWidth, editable: true, suppressMovable: true }];
    const dynamicCols = dateColumns.map(date => ({
      field: date,
      headerName: date,
      editable: true,
      cellEditor: 'agNumberCellEditor',
      type: 'numericColumn',
      width: colWidth,
      suppressMovable: true,
      cellStyle: (params) => {
        if (isWeekend(params.colDef.field)) {
          return { backgroundColor: '#f1f5f9' };
        }
        return null;
      },
      cellRenderer: (params) => {
        const val = params.value;
        if (val === null || val === undefined || val === '') {
          return <span className="empty-placeholder text-gray-400 italic text-xs">Quota</span>;
        }
        return <span className="text-gray-800 font-medium">{val}</span>;
      }
    }));
    return [...baseCols, ...dynamicCols];
  }, [dateColumns, pinColWidth, colWidth]);

  const handleTeamGridReady = (params) => {
    setTopGridApi(params.api);
    if (teamWrapperRef.current) {
      const rowCount = params.api.getDisplayedRowCount() || 4;
      teamWrapperRef.current.style.height = `${calcDefaultHeight(rowCount)}px`;
    }
  };

  const handleAddTeamRow = () => {
    setTeamRowData(prevData => {
      const updatedData = [...prevData, {
        teamName: ''
      }];

      if (teamWrapperRef.current) {
        const rowCount = updatedData.length;
        teamWrapperRef.current.style.height = `${calcDefaultHeight(rowCount)}px`;
      }

      return updatedData;
    });
  };

  const onTeamCellEditingStopped = async (params) => {
    const { colDef, newValue, oldValue, node } = params;
    
    if (colDef.field === 'teamName' && newValue !== oldValue) {
      setTeamRowData(prev => 
        prev.map((row, index) => 
          index === node.rowIndex ? { ...row, teamName: newValue } : row
        )
      );

      await fetch('/api/teams/update', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rowIndex: node.rowIndex, teamName: newValue })
      });
    }
  };

  // --- Dynamically Build Call Column Definitions ---
  const callColumnDefs = useMemo(() => {
    const baseCols = [{ field: 'callName', headerName: 'Call', pinned: 'left', width: pinColWidth, editable: true, suppressMovable: true }];
    const dynamicCols = dateColumns.map(date => ({
      field: date,
      headerName: date,
      editable: true,
      cellEditor: 'agNumberCellEditor',
      type: 'numericColumn',
      width: colWidth,
      suppressMovable: true,
      cellStyle: (params) => {
        if (isWeekend(params.colDef.field)) {
          return { backgroundColor: '#f1f5f9' };
        }
        return null;
      },
      cellRenderer: (params) => {
        const val = params.value;
        if (val === null || val === undefined || val === '') {
          return <span className="empty-placeholder text-gray-400 italic text-xs">Quota</span>;
        }
        return <span className="text-gray-800 font-medium">{val}</span>;
      }
    }));
    return [...baseCols, ...dynamicCols];
  }, [dateColumns, pinColWidth, colWidth]);

  const handleCallGridReady = (params) => {
    setMiddleGridApi(params.api);
    if (callWrapperRef.current) {
      const rowCount = params.api.getDisplayedRowCount() || 4;
      callWrapperRef.current.style.height = `${calcDefaultHeight(rowCount)}px`;
    }
  };

  // --- Dynamically Build Personnel Column Definitions (Double Column System) ---
  const rosterColumnDefs = useMemo(() => {
    const baseCols = [{ field: 'name', headerName: 'Roster', pinned: 'left', width: pinColWidth, editable: true, suppressMovable: true }];
    
    const dynamicCols = dateColumns.map(date => {
      // Team Sub-Column
      const teamSubCol = {
        field: `${date}_team`,
        headerName: rosterViewMode === 'both' ? 'Team' : date,
        editable: true,
        width: rosterViewMode === 'both' ? Math.floor(colWidth / 2) : colWidth,
        suppressMovable: true,
        cellStyle: isWeekend(date) ? { backgroundColor: '#f1f5f9' } : null,
        valueGetter: (params) => params.data[date]?.team || '',
        valueSetter: (params) => {
          const rowIndex = params.node.rowIndex;
          const newTeam = params.newValue;
          setRosterTeamRowData(prev => {
            const updated = [...prev];
            updated[rowIndex] = { ...updated[rowIndex], [date]: newTeam };
            return updated;
          });
          return true;
        },
        cellEditor: 'agRichSelectCellEditor',
        cellEditorParams: {
          values: availableTeams,
          searchEnabled: true,
          highlightMatch: true,
        },
        cellRenderer: (params) => {
          const teamVal = params.data[date]?.team;
          if (!teamVal) return <span className="empty-placeholder text-xs text-gray-400 italic">Team</span>;
          return <span className="text-gray-800 font-medium">{teamVal}</span>;
        }
      };

      // Call Sub-Column (Dropdown matching Team cell behavior)
      const callSubCol = {
        field: `${date}_call`,
        headerName: rosterViewMode === 'both' ? 'Call' : date,
        editable: true,
        width: rosterViewMode === 'both' ? Math.floor(colWidth / 2) : colWidth,
        suppressMovable: true,
        cellStyle: isWeekend(date) ? { backgroundColor: '#f1f5f9' } : null,
        
        // Convert stored boolean to display string for the dropdown
        valueGetter: (params) => {
          const val = params.data[date]?.call;
          if (val === true) return 'True';
          if (val === false) return 'False';
          return ''; // Unset / Default
        },

        // Convert selected dropdown string back to a boolean or empty state
        valueSetter: (params) => {
          const rowIndex = params.node.rowIndex;
          const strVal = params.newValue;
          
          let newVal = '';
          if (strVal === 'True') newVal = true;
          else if (strVal === 'False') newVal = false;

          setRosterCallRowData(prev => {
            const updated = [...prev];
            updated[rowIndex] = { ...updated[rowIndex], [date]: newVal };
            return updated;
          });
          return true;
        },

        // Use the rich select editor just like the team cell
        cellEditor: 'agRichSelectCellEditor',
        cellEditorParams: {
          values: ['True', 'False'],
        },

        // Grayed-out placeholder when unset, matching team cell styling
        cellRenderer: (params) => {
          const val = params.data[date]?.call;
          if (val === '' || val === null || val === undefined) {
            return <span className="empty-placeholder text-xs text-gray-400 italic">Call</span>;
          }
          if (val === true) {
            return <span className="text-indigo-600 font-semibold">True</span>;
          }
          return <span className="text-red-500 font-semibold">False</span>;
        }
      };

      if (rosterViewMode === 'teams') return teamSubCol;
      if (rosterViewMode === 'calls') return callSubCol;

      // 'both' mode: Grouped parent column
      return {
        headerName: date,
        headerClass: isWeekend(date) ? 'bg-slate-100' : '',
        children: [teamSubCol, callSubCol]
      };
    });

    return [...baseCols, ...dynamicCols];
  }, [dateColumns, rosterViewMode, pinColWidth, colWidth, availableTeams]);

  const handleRosterGridReady = (params) => {
    setBottomGridApi(params.api);
  };

  const handleAddRosterRow = () => {
    const emptyRow = {
      name: '',
      ...dateColumns.reduce((acc, date) => ({ ...acc, [date]: '' }), {})
    };

    setRosterTeamRowData(prev => [...prev, emptyRow]);
    setRosterCallRowData(prev => [...prev, emptyRow]);
  };

  const onRosterCellStoppedEditing = async (params) => {
    const { data, colDef } = params;
    const cellData = data[colDef.field];
    if (!cellData) return;
      
    await fetch('/api/roster/cell', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        row: params.node.rowIndex, 
        date: colDef.field, 
        data: cellData 
      })
    });
  };

  const customThemeBalham = themeBalham.withParams({
    borderColor: '#cbd5e1',
    rowBorder: '1px solid #cbd5e1',
    columnBorder: '1px solid #cbd5e1'
  });

  const handleCellKeyDown = (params) => {
    const { event, api } = params;
    
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
      event.preventDefault();
      
      const allColumns = api.getColumns();
      const unpinnedColumns = allColumns.filter(col => {
        const colDef = col.getColDef();
        return colDef.pinned !== 'left' && colDef.pinned !== 'right';
      });

      if (unpinnedColumns.length === 0) return;

      const firstCol = unpinnedColumns[0];
      const lastCol = unpinnedColumns[unpinnedColumns.length - 1];
      const lastRowIndex = api.getDisplayedRowCount() - 1;

      api.clearCellSelection();
      api.addCellRange({
        rowStartIndex: 0,
        rowEndIndex: lastRowIndex,
        columnStart: firstCol,
        columnEnd: lastCol,
      });
    }
  };

  const handleCellChanged = (setter) => (params) => {
    setter(prevData => {
      const updated = [...prevData];
      updated[params.node.rowIndex] = { ...params.data };
      return updated;
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white py-2">
        <div>
          <h2 className="text-xl font-bold text-gray-800">team & calls roster thing</h2>
        </div>

        {/* Date Range Controls */}
        <div className="flex items-center gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Start Date</label>
            <input 
              type="date" 
              value={startDate} 
              onChange={(e) => setStartDate(e.target.value)}
              className="border border-gray-300 rounded px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">End Date</label>
            <input 
              type="date" 
              value={endDate} 
              onChange={(e) => setEndDate(e.target.value)}
              className="border border-gray-300 rounded px-3 py-1.5 text-sm"
            />
          </div>
          <button 
            onClick={() => alert("Packaging timeline data to POST /api/roster/run-model")}
            className="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700 transition self-end text-sm font-medium"
          >
            Run Optimization Model
          </button>
        </div>
      </div>

      {/* TOP TABLE: Team Requirements */}
      <div className="">
        <div className="flex justify-between items-center mb-1">
          <h3 className="text-xs font-bold tracking-wider text-gray-400 mb-2">Personnel Assignment & Call Roster</h3>
          <button 
            onClick={handleAddTeamRow}
            className="mb-2 px-3 py-1 text-xs font-semibold text-white bg-gray-400 hover:bg-gray-600 rounded-md transition-colors"
          >
            +Row
          </button>
        </div>
        <div ref={teamWrapperRef} className="resize-y overflow-auto min-h-[50px] max-h-[500px]">
          <AgGridReact
            theme={customThemeBalham}
            rowData={teamRowData}
            columnDefs={teamColumnDefs}
            defaultColDef={defaultColDef}
            suppressMovableColumns={true}
            onGridReady={handleTeamGridReady}
            onColumnResized={handleColumnResized}
            alignedGrids={[middleGridApi, bottomGridApi].filter(Boolean)}

            onCellEditingStopped={onTeamCellEditingStopped}
            stopEditingWhenCellsLoseFocus={true}
            onCellKeyDown={handleCellKeyDown}
            onCellValueChanged={handleCellChanged(setTeamRowData)}

            cellSelection={{
              handle: { mode: 'fill' }
            }}
            enableFillHandle={true}
            undoRedoCellEditing={true}
            undoRedoCellEditingLimit={20}
            suppressRowClickSelection={true}
            enterNavigatesVertically={true}
            enterNavigatesVerticallyAfterEdit={true}
          />
        </div>
      </div>

      {/* MIDDLE TABLE: Call Requirements */}
      <div className="">
        <h3 className="text-xs font-bold tracking-wider text-gray-400 mb-2">Team Requirements Configuration</h3>
        <div ref={callWrapperRef} className="resize-y overflow-auto block min-h-[40px] max-h-[600px]">
          <AgGridReact
            theme={customThemeBalham}
            rowData={callRowData}
            defaultColDef={defaultColDef}
            columnDefs={callColumnDefs}
            suppressMovableColumns={true}
            onGridReady={handleCallGridReady}
            onColumnResized={handleColumnResized}
            alignedGrids={[topGridApi, bottomGridApi].filter(Boolean)}

            stopEditingWhenCellsLoseFocus={true}
            onCellKeyDown={handleCellKeyDown}
            onCellValueChanged={handleCellChanged(setTeamRowData)}

            cellSelection={{
              handle: { mode: 'fill' }
            }}
            enableFillHandle={true}
            undoRedoCellEditing={true}
            undoRedoCellEditingLimit={20}
            suppressRowClickSelection={true}
            enterNavigatesVertically={true}
            enterNavigatesVerticallyAfterEdit={true}
          />
        </div>
      </div>

      {/* BOTTOM TABLE: Personnel Shifts */}
      <div className="">
        <div className="flex justify-between items-center mb-1">
          <div className="flex items-center gap-4 mb-2">
            <h3 className="text-xs font-bold tracking-wider text-gray-400">Personnel Assignment & Call Roster</h3>
            
            {/* View Mode Toggle Buttons */}
            <div className="inline-flex rounded-md shadow-sm bg-gray-100 p-0.5 text-xs">
              <button
                onClick={() => setRosterViewMode('teams')}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${rosterViewMode === 'teams' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
              >
                Teams Only
              </button>
              <button
                onClick={() => setRosterViewMode('calls')}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${rosterViewMode === 'calls' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
              >
                Calls Only
              </button>
              <button
                onClick={() => setRosterViewMode('both')}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${rosterViewMode === 'both' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
              >
                Both
              </button>
            </div>
          </div>

          <button 
              onClick={handleAddRosterRow}
              className="mb-2 px-3 py-1 text-xs font-semibold text-white bg-gray-400 hover:bg-gray-600 rounded-md transition-colors"
            >
            +Row
          </button>
        </div>
        <div ref={rosterWrapperRef} className="resize-y overflow-auto min-h-[100px] max-h-[600px]">
          <AgGridReact
            theme={customThemeBalham}
            rowData={rosterGridRowData}
            columnDefs={rosterColumnDefs}
            defaultColDef={defaultColDef}
            suppressMovableColumns={true}
            onGridReady={handleRosterGridReady}
            onCellStoppedEditing={onRosterCellStoppedEditing}
            stopEditingWhenCellsLoseFocus={true}  
            alignedGrids={[topGridApi, middleGridApi].filter(Boolean)}

            onColumnResized={handleColumnResized}
            onCellKeyDown={handleCellKeyDown}

            cellSelection={{
              handle: { mode: 'fill' }
            }}
            undoRedoCellEditing={true}  
            undoRedoCellEditingLimit={20}
            suppressRowClickSelection={true}
            enterNavigatesVertically={true}
            enterNavigatesVerticallyAfterEdit={true}
          />
        </div>
      </div>

      <pre>{JSON.stringify(teamRowData, null, 2)}</pre>
      <pre>{JSON.stringify(callRowData, null, 2)}</pre>
      <pre>{JSON.stringify({ rosterTeamRowData, rosterCallRowData }, null, 2)}</pre>
    </div>
  );
}