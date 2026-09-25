import React, { useState, useMemo, useRef } from 'react';
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

  const [pinColWidth, setPinColWidth] = useState(100)
  const [colWidth, setColWidth] = useState(120)

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
  ])

  // Dynamically extract team names from top table to feed bottom dropdown
  const availableTeams = useMemo(() => {
    return teamRowData.map(row => row.teamName).filter(Boolean);
  }, [teamRowData]);

  // --- Initial Personnel Roster Data ---
  const [rosterRowData, setRosterRowData] = useState([
    { name: 'Person 1' },
    { name: 'Person 2' },
    { name: 'Person 3' },
    { name: 'Person 4' },
  ]);

  const teamWrapperRef = useRef(null);
  const callWrapperRef = useRef(null);
  const rosterWrapperRef = useRef(null);

  const calcDefaultHeight = ((rowCount) => {
    return 33 + (rowCount * 29) + 18;
  })

  const isResizingRef = useRef(false);

  const handleColumnResized = (params) => {
    if (isResizingRef.current) return;
    
    // Only sync once the user finishes dragging the column edge
    if (!params.finished) return;

    const resizedCol = params.column;
    if (!resizedCol) return;

    const newWidth = resizedCol.getActualWidth();
    const isPinned = resizedCol.isPinned();
    
    isResizingRef.current = true;

    // Get all active grid instances
    const allGrids = [topGridApi, bottomGridApi, middleGridApi].filter(Boolean);

    if (isPinned) {
      setPinColWidth(newWidth)
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
      setColWidth(newWidth)
      allGrids.forEach(gridApi => {
        const allCols = gridApi.getColumns();
        const dateColIds = allCols
          .filter(col => !col.isPinned())
          .map(col => col.getColId());
        
        gridApi.applyColumnState({
          state: dateColIds.map(id => ({
            colId: id,
            width: newWidth
          }))
        });
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
      // Highlight weekends with a subtle darker grey background
      cellStyle: (params) => {
        if (isWeekend(params.colDef.field)) {
          return { backgroundColor: '#f1f5f9' }; // Tailwind slate-100 equivalent
        }
        return null;
      },
      cellRenderer: (params) => {
        const val = params.value;
        if (val === null || val === undefined || val === '') {
          return <span className="empty-placeholder text-gray-400 italic text-xs">Quota...</span>;
        }
        return <span className="text-gray-800 font-medium">{val}</span>;
      }
    }));
    return [...baseCols, ...dynamicCols];
  }, [dateColumns]);

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
        name: ''
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
      // Highlight weekends
      cellStyle: (params) => {
        if (isWeekend(params.colDef.field)) {
          return { backgroundColor: '#f1f5f9' };
        }
        return null;
      },
      cellRenderer: (params) => {
        const val = params.value;
        if (val === null || val === undefined || val === '') {
          return <span className="empty-placeholder text-gray-400 italic text-xs">Calls...</span>;
        }
        return <span className="text-gray-800 font-medium">{val}</span>;
      }
    }));
    return [...baseCols, ...dynamicCols];
  }, [dateColumns]);

  const handleCallGridReady = (params) => {
    setMiddleGridApi(params.api);
    if (callWrapperRef.current) {
      const rowCount = params.api.getDisplayedRowCount() || 4;
      callWrapperRef.current.style.height = `${calcDefaultHeight(rowCount)}px`;
    }
  };

  // --- Dynamically Build Personnel Column Definitions ---
  const rosterColumnDefs = useMemo(() => {
    const baseCols = [{ field: 'name', headerName: 'Roster', pinned: 'left', width: pinColWidth, editable: true, suppressMovable: true }];
    const dynamicCols = dateColumns.map(date => ({
      field: date,
      headerName: date,
      editable: true,
      width: colWidth,
      suppressMovable: true,
      // Highlight weekends
      cellStyle: (params) => {
        if (isWeekend(params.colDef.field)) {
          return { backgroundColor: '#f1f5f9' };
        }
        return null;
      },
      valueGetter: (params) => {
        return params.data[date]?.team || '';
      },
      valueSetter: (params) => {
        const newTeam = params.newValue;
        const currentData = params.data[date] || {};
        params.data[date] = {
          ...currentData,
          team: newTeam,
          source: 'manual',
          locked: true
        };
        return true;
      },
      cellEditor: 'agRichSelectCellEditor',
      cellEditorParams: {
        values: availableTeams,
        searchEnabled: true,
        highlightMatch: true,
      },
      cellRenderer: (params) => {
        const currentData = params.data[date];
        const teamVal = currentData?.team;

        if (!teamVal) {
          return <span className="empty-placeholder text-xs">Team...</span>;
        }

        const isManual = currentData.source === 'manual';
        return (
          <span className={isManual ? 'text-blue-700 font-semibold' : 'text-gray-800'}>
            {teamVal} {currentData.onCall ? '📞' : ''} {isManual && '🔒'}
          </span>
        );
      }
    }));
    return [...baseCols, ...dynamicCols];
  }, [dateColumns, availableTeams]);

  const handleRosterGridReady = (params) => {
    setBottomGridApi(params.api);
    if (rosterWrapperRef.current) {
      const rowCount = params.api.getDisplayedRowCount() || 4;
      rosterWrapperRef.current.style.height = `${calcDefaultHeight(rowCount)}px`;
    }
  };

  const handleAddRosterRow = () => {
    setRosterRowData(prevData => {
      const updatedData = [...prevData, {
        name: ''
      }];

      if (rosterWrapperRef.current) {
        const rowCount = updatedData.length;
        rosterWrapperRef.current.style.height = `${calcDefaultHeight(rowCount)}px`;
      }

      return updatedData;
    });
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
            className="bg-indigo-600 text-white px-4 py-2 rounded shadow hover:bg-indigo-700 transition self-end text-sm font-medium"
          >
            Run Optimization Model
          </button>
        </div>
      </div>

      {/* TOP TABLE: Team Requirements */}
      <div className="">
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-xs font-bold tracking-wider text-gray-400 mb-2">Personnel Assignment & Call Roster</h3>
          <button 
            onClick={handleAddTeamRow}
            className="mb-2 px-3 py-1 text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-gray-100 hover:text-indigo-900 rounded-md transition-colors"
          >
            +Row
          </button>
        </div>
        <div ref={teamWrapperRef} className="resize-y overflow-auto min-h-[50px] max-h-[500px]">
          <AgGridReact
            theme={customThemeBalham}
            rowData={teamRowData}
            columnDefs={teamColumnDefs}
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
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-xs font-bold tracking-wider text-gray-400 mb-2">Personnel Assignment & Call Roster</h3>
          <button 
              onClick={handleAddRosterRow}
              className="px-3 py-1 text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-gray-100 hover:text-indigo-900 rounded-md transition-colors"
            >
            +Row
          </button>
        </div>
        <div ref={rosterWrapperRef} className="resize-y overflow-auto min-h-[100px] max-h-[600px]">
          <AgGridReact
            theme={customThemeBalham}
            rowData={rosterRowData}
            columnDefs={rosterColumnDefs}
            suppressMovableColumns={true}
            onGridReady={handleRosterGridReady}
            onCellStoppedEditing={onRosterCellStoppedEditing}
            stopEditingWhenCellsLoseFocus={true}  
            alignedGrids={[topGridApi, middleGridApi].filter(Boolean)}

            onColumnResized={handleColumnResized}
            onCellKeyDown={handleCellKeyDown}
            onCellValueChanged={handleCellChanged(setTeamRowData)}

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
      <pre>{JSON.stringify(rosterRowData, null, 2)}</pre>
    </div>
  );
}