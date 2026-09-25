import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { AllEnterpriseModule, ModuleRegistry, themeBalham } from 'ag-grid-enterprise';

ModuleRegistry.registerModules([AllEnterpriseModule]);

const getDatesBetween = (startStr, endStr) => {
  const dates = [];
  let currentDate = new Date(startStr);
  const endDate = new Date(endStr);

  while (currentDate <= endDate) {
    dates.push(currentDate.toISOString().split('T')[0]);
    currentDate.setDate(currentDate.getDate() + 1);
  }
  return dates;
};

const isWeekend = (dateStr) => {
  const d = new Date(dateStr);
  const day = d.getDay();
  return day === 0 || day === 6;
};

export default function DynamicRosterGrid() {
  const [topGridApi, setTopGridApi] = useState(null);
  const [middleGridApi, setMiddleGridApi] = useState(null);
  const [bottomGridApi, setBottomGridApi] = useState(null);

  const [startDate, setStartDate] = useState('2026-09-01');
  const [endDate, setEndDate] = useState('2026-09-30');

  const [minCallInterval, setMinCallInterval] = useState(2);
  const [maxTeamsPerWeek, setMaxTeamsPerWeek] = useState(1);
  const [maxSolveTime, setMaxSolveTime] = useState(60);
  const [alCallBufferBefore, setAlCallBufferBefore] = useState(1);
  const [alCallBufferAfter, setAlCallBufferAfter] = useState(0);
  const [blockoutCallBufferBefore, setBlockoutCallBufferBefore] = useState(1);
  const [blockoutCallBufferAfter, setBlockoutCallBufferAfter] = useState(0);

  const [showSettings, setShowSettings] = useState(false);
  const [isSolving, setIsSolving] = useState(false);
  const [solveMessage, setSolveMessage] = useState('');
  
  const [saveStatus, setSaveStatus] = useState('All changes saved');
  const [pendingCount, setPendingCount] = useState(0);

  const dateColumns = useMemo(() => getDatesBetween(startDate, endDate), [startDate, endDate]);

  const [pinColWidth, setPinColWidth] = useState(100);
  const [colWidth, setColWidth] = useState(120);
  const defaultColDef = useMemo(() => ({ suppressHeaderMenuButton: true }), []);

  const [rosterViewMode, setRosterViewMode] = useState('both');

  const [teamRowData, setTeamRowData] = useState([
    { teamName: 'Team A' },
    { teamName: 'Team B' },
    { teamName: 'Team C' },
    { teamName: 'Team D' },
  ]);

  const [callRowData, setCallRowData] = useState([
    { callName: "Call 1" }
  ]);

  const availableTeams = useMemo(() => {
    return teamRowData.map(row => row.teamName).filter(Boolean);
  }, [teamRowData]);

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

  // --- ASYNC BATCH QUEUE & REFS ---
  const dirtyQueueRef = useRef(new Map());
  const saveTimeoutRef = useRef(null);

  const flushQueue = async () => {
    if (dirtyQueueRef.current.size === 0) return;

    const updates = Array.from(dirtyQueueRef.current.values());
    dirtyQueueRef.current.clear();
    setPendingCount(0);
    setSaveStatus('Saving changes...');

    try {
      const response = await fetch('http://localhost:8000/api/roster/batch-cells', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates })
      });

      if (!response.ok) throw new Error('Network response was not ok');
      setSaveStatus('All changes saved');
    } catch (err) {
      console.error("Batch sync failed:", err);
      setSaveStatus('⚠️ Save failed! Retrying...');
      updates.forEach(u => dirtyQueueRef.current.set(`${u.table_type}-${u.row_index}-${u.field}`, u));
      setPendingCount(dirtyQueueRef.current.size);
    }
  };

  const queueCellUpdate = useCallback((tableType, rowIndex, field, value) => {
    const key = `${tableType}-${rowIndex}-${field}`;
    dirtyQueueRef.current.set(key, { table_type: tableType, row_index: rowIndex, field, value });
    
    const count = dirtyQueueRef.current.size;
    setPendingCount(count);
    setSaveStatus(`Unsaved changes (${count})...`);

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(() => {
      flushQueue();
    }, 500);
  }, []);

  // --- ASYNC NON-BLOCKING STATE UPDATER ---
  const updateStateAsync = useCallback((setter, updaterFn) => {
    requestAnimationFrame(() => {
      setter(updaterFn);
    });
  }, []);

  useEffect(() => {
    const handleBeforeUnload = () => {
      if (dirtyQueueRef.current.size > 0) flushQueue();
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    fetch('http://localhost:8000/api/roster/state')
      .then(res => res.json())
      .then(data => {
        if (data.start_date) setStartDate(data.start_date);
        if (data.end_date) setEndDate(data.end_date);
        if (data.min_call_interval !== undefined) setMinCallInterval(data.min_call_interval);
        if (data.max_teams_per_week !== undefined) setMaxTeamsPerWeek(data.max_teams_per_week);
        if (data.max_solve_time !== undefined) setMaxSolveTime(data.max_solve_time);
        if (data.al_call_buffer_before !== undefined) setAlCallBufferBefore(data.al_call_buffer_before);
        if (data.al_call_buffer_after !== undefined) setAlCallBufferAfter(data.al_call_buffer_after);
        if (data.blockout_call_buffer_before !== undefined) setBlockoutCallBufferBefore(data.blockout_call_buffer_before);
        if (data.blockout_call_buffer_after !== undefined) setBlockoutCallBufferAfter(data.blockout_call_buffer_after);

        if (data.team_row_data) setTeamRowData(data.team_row_data);
        if (data.call_row_data) setCallRowData(data.call_row_data);
        if (data.roster_team_row_data) setRosterTeamRowData(data.roster_team_row_data);
        if (data.roster_call_row_data) setRosterCallRowData(data.roster_call_row_data);
      })
      .catch(err => console.error("Failed to load backend state:", err));
  }, []);

  const updateBackendSettings = async (updatedSettings) => {
    setSaveStatus('Saving settings...');
    try {
      await fetch('http://localhost:8000/api/roster/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: updatedSettings })
      });
      setSaveStatus('All changes saved');
    } catch (err) {
      console.error("Failed to sync settings:", err);
      setSaveStatus('Error saving settings!');
    }
  };

  const rosterGridRowData = useMemo(() => {
    return rosterTeamRowData.map((teamRow, index) => {
      const callRow = rosterCallRowData[index] || { name: teamRow.name };
      const merged = { name: teamRow.name };
      
      dateColumns.forEach(date => {
        const callVal = callRow[date];
        merged[date] = {
          team: teamRow[date] || '',
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

  useEffect(() => {
    if (rosterWrapperRef.current) {
      const rowCount = bottomGridApi ? bottomGridApi.getDisplayedRowCount() : rosterTeamRowData.length;
      const headers = rosterViewMode === 'both' ? 2 : 1;
      rosterWrapperRef.current.style.height = `${calcDefaultHeight(Math.max(rowCount, 1), headers)}px`;
    }
  }, [rosterViewMode, bottomGridApi, rosterTeamRowData.length]);

  useEffect(() => {
    if (teamWrapperRef.current) {
      const rowCount = topGridApi ? topGridApi.getDisplayedRowCount() : teamRowData.length;
      teamWrapperRef.current.style.height = `${calcDefaultHeight(Math.max(rowCount, 1))}px`;
    }
  }, [topGridApi, teamRowData.length]);

  useEffect(() => {
    if (callWrapperRef.current) {
      const rowCount = middleGridApi ? middleGridApi.getDisplayedRowCount() : callRowData.length;
      callWrapperRef.current.style.height = `${calcDefaultHeight(Math.max(rowCount, 1))}px`;
    }
  }, [middleGridApi, callRowData.length]);

  const isResizingRef = useRef(false);

  const handleColumnResized = (params) => {
    if (isResizingRef.current) return;
    if (!params.finished && params.source !== 'uiColumnDragged') return;

    const resizedCol = params.column;
    const affectedCols = params.columns;
    const isPinned = resizedCol ? resizedCol.isPinned() : false;
    
    isResizingRef.current = true;
    const allGrids = [topGridApi, bottomGridApi, middleGridApi].filter(Boolean);

    if (isPinned) {
      if (!resizedCol) { isResizingRef.current = false; return; }
      const newWidth = resizedCol.getActualWidth();
      if (newWidth > 40) {
        setPinColWidth(newWidth);
        allGrids.forEach(gridApi => {
          const targetPinnedCols = gridApi.getColumns().filter(col => col.isPinned());
          const pinnedIndex = gridApi.getColumns().filter(col => col.isPinned()).indexOf(resizedCol);
          if (targetPinnedCols[pinnedIndex]) {
            gridApi.applyColumnState({ state: [{ colId: targetPinnedCols[pinnedIndex].getColId(), width: newWidth }] });
          }
        });
      }
    } else {
      const targetColToMeasure = resizedCol || (affectedCols && affectedCols[0]);
      let rawWidth = targetColToMeasure ? targetColToMeasure.getActualWidth() : colWidth;
      
      if (rawWidth > 40) {
        let newColWidth = rawWidth;
        if (bottomGridApi && rosterViewMode === 'both' && affectedCols && affectedCols.length === 2) {
          newColWidth = affectedCols.reduce((sum, col) => sum + Math.max(col.getActualWidth(), 30), 0);
        }

        setColWidth(newColWidth);

        allGrids.forEach(gridApi => {
          const unpinnedCols = gridApi.getColumns().filter(col => !col.isPinned());
          const targetIsRosterBoth = (gridApi === bottomGridApi && rosterViewMode === 'both');

          if (targetIsRosterBoth) {
            const halfWidth = Math.max(Math.floor(newColWidth / 2), 30);
            gridApi.applyColumnState({ 
              state: unpinnedCols.map(col => ({ colId: col.getColId(), width: halfWidth })) 
            });
          } else {
            gridApi.applyColumnState({ 
              state: unpinnedCols.map(col => ({ colId: col.getColId(), width: newColWidth })) 
            });
          }
        });
      }
    }

    requestAnimationFrame(() => { isResizingRef.current = false; });
  };

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
      valueParser: (params) => {
        if (params.newValue === '' || params.newValue === null || params.newValue === undefined) {
          return '';
        }
        const parsed = Number(params.newValue);
        return isNaN(parsed) ? params.oldValue : parsed;
      },
      valueFormatter: (params) => {
        return params.value !== null && params.value !== undefined ? params.value : '';
      },
      cellStyle: (params) => isWeekend(params.colDef.field) ? { backgroundColor: '#f1f5f9' } : null,
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
  };

  const handleAddTeamRow = () => {
    const newRow = { teamName: `Team ${teamRowData.length + 1}` };
    dateColumns.forEach(date => { newRow[date] = ''; });
    updateStateAsync(setTeamRowData, prev => [...prev, newRow]);
  };

  const onTeamCellValueChanged = async (event) => {
    const { column, oldValue, newValue, node } = event;
    if (oldValue === newValue) return;

    if (column.getColId() === 'teamName') {
      setSaveStatus('Updating team name...');
      try {
        await fetch('http://localhost:8000/api/teams/update', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ originalTeamName: oldValue, teamName: newValue })
        });
        setSaveStatus('All changes saved');
      } catch (err) {
        console.error("Failed to update team name:", err);
        setSaveStatus('⚠️ Update team name failed');
      }
    } else {
      // Synchronous state update prevents race condition on Enter/Edit completion
      setTeamRowData(prev => {
        const updated = [...prev];
        updated[node.rowIndex] = { ...node.data };
        return updated;
      });
      queueCellUpdate('team', node.rowIndex, column.getColId(), newValue);
    }
  };

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
      valueParser: (params) => {
        if (params.newValue === '' || params.newValue === null || params.newValue === undefined) {
          return '';
        }
        const parsed = Number(params.newValue);
        return isNaN(parsed) ? params.oldValue : parsed;
      },
      valueFormatter: (params) => {
        return params.value !== null && params.value !== undefined ? params.value : '';
      },
      cellStyle: (params) => isWeekend(params.colDef.field) ? { backgroundColor: '#f1f5f9' } : null,
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
  };

  const onCallCellValueChanged = (event) => {
    const { node, column, oldValue, newValue } = event;
    if (oldValue === newValue) return;

    // Synchronous state update prevents race condition on Enter/Edit completion
    setCallRowData(prev => {
      const updated = [...prev];
      updated[node.rowIndex] = { ...node.data };
      return updated;
    });
    queueCellUpdate('call_req', node.rowIndex, column.getColId(), newValue);
  };

  const rosterColumnDefs = useMemo(() => {
    const baseCols = [{ field: 'name', headerName: 'Roster', pinned: 'left', width: pinColWidth, editable: true, suppressMovable: true }];
    
    const dynamicCols = dateColumns.map(date => {
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
          updateStateAsync(setRosterTeamRowData, prev => {
            const updated = [...prev];
            updated[rowIndex] = { ...updated[rowIndex], [date]: newTeam };
            return updated;
          });
          queueCellUpdate('roster_team', rowIndex, date, newTeam);
          return true;
        },
        cellEditor: 'agRichSelectCellEditor',
        cellEditorParams: { 
          values: availableTeams, 
          searchEnabled: true, 
          highlightMatch: true,
          allowTyping: true,
          filterList: true
        },
        cellRenderer: (params) => {
          const teamVal = params.data[date]?.team;
          if (!teamVal) return <span className="empty-placeholder text-xs text-gray-400 italic">Team</span>;
          return <span className="text-gray-800 font-medium">{teamVal}</span>;
        }
      };

      const callSubCol = {
        field: `${date}_call`,
        headerName: rosterViewMode === 'both' ? 'Call' : date,
        editable: true,
        width: rosterViewMode === 'both' ? Math.floor(colWidth / 2) : colWidth,
        suppressMovable: true,
        cellStyle: isWeekend(date) ? { backgroundColor: '#f1f5f9' } : null,
        valueGetter: (params) => {
          const val = params.data[date]?.call;
          if (val === true) return 'True';
          if (val === false) return 'False';
          return '';
        },
        valueSetter: (params) => {
          const rowIndex = params.node.rowIndex;
          const strVal = params.newValue;
          let newVal = strVal === 'True' ? true : strVal === 'False' ? false : '';

          updateStateAsync(setRosterCallRowData, prev => {
            const updated = [...prev];
            updated[rowIndex] = { ...updated[rowIndex], [date]: newVal };
            return updated;
          });
          queueCellUpdate('roster_call', rowIndex, date, newVal);
          return true;
        },
        cellEditor: 'agRichSelectCellEditor',
        cellEditorParams: { 
          values: ['True', 'False'],
          allowTyping: true,
          filterList: true
        },
        cellRenderer: (params) => {
          const val = params.data[date]?.call;
          if (val === '' || val === null || val === undefined) {
            return <span className="empty-placeholder text-xs text-gray-400 italic">Call</span>;
          }
          if (val === true) return <span className="text-indigo-600 font-semibold">True</span>;
          return <span className="text-red-500 font-semibold">False</span>;
        }
      };

      if (rosterViewMode === 'teams') return teamSubCol;
      if (rosterViewMode === 'calls') return callSubCol;

      return {
        headerName: date,
        headerClass: isWeekend(date) ? 'bg-slate-100' : '',
        children: [teamSubCol, callSubCol]
      };
    });

    return [...baseCols, ...dynamicCols];
  }, [dateColumns, rosterViewMode, pinColWidth, colWidth, availableTeams, updateStateAsync, queueCellUpdate]);

  const handleRosterGridReady = (params) => {
    setBottomGridApi(params.api);
  };

  const handleAddRosterRow = () => {
    const newName = `Person ${rosterTeamRowData.length + 1}`;
    const newTeamRow = { name: newName };
    const newCallRow = { name: newName };
    dateColumns.forEach(date => { 
      newTeamRow[date] = ''; 
      newCallRow[date] = ''; 
    });
    updateStateAsync(setRosterTeamRowData, prev => [...prev, newTeamRow]);
    updateStateAsync(setRosterCallRowData, prev => [...prev, newCallRow]);
  };

  const triggerOptimizationModel = async () => {
    await flushQueue();

    setIsSolving(true);
    setSolveMessage('Optimization model running in background...');

    try {
      const res = await fetch('http://localhost:8000/api/roster/run-model', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_date: startDate, end_date: endDate })
      });
      const data = await res.json();
      
      const stateRes = await fetch('http://localhost:8000/api/roster/state');
      const stateData = await stateRes.json();
      if (stateData.roster_team_row_data) updateStateAsync(setRosterTeamRowData, stateData.roster_team_row_data);
      if (stateData.roster_call_row_data) updateStateAsync(setRosterCallRowData, stateData.roster_call_row_data);

      setSolveMessage(data.message || "Model execution completed successfully.");
    } catch (err) {
      setSolveMessage("Failed to communicate with optimization backend.");
    } finally {
      setTimeout(() => setIsSolving(false), 4000);
    }
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

      api.clearCellSelection();
      api.addCellRange({
        rowStartIndex: 0,
        rowEndIndex: api.getDisplayedRowCount() - 1,
        columnStart: unpinnedColumns[0],
        columnEnd: unpinnedColumns[unpinnedColumns.length - 1],
      });
    }
  };

  const isSaved = saveStatus.includes('saved');

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 relative pb-16">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white py-2">
        <div>
          <h2 className="text-xl font-bold text-gray-800">Team & Calls Roster Workbench</h2>
          
          <div className="flex items-center gap-2 mt-1">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
              isSaved 
                ? 'bg-emerald-50 text-emerald-700' 
                : 'bg-amber-50 text-amber-700'
            }`}>
              {/* <span className={`w-2 h-2 rounded-full ${isSaved ? 'bg-emerald-500' : 'bg-amber-500'}`}></span> */}
              {saveStatus}
            </span>
            {pendingCount > 0 && (
              <span className="text-[11px] text-gray-400 font-medium">
                ({pendingCount} queued change{pendingCount > 1 ? 's' : ''})
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Start Date</label>
            <input 
              type="date" 
              value={startDate} 
              onChange={(e) => {
                const val = e.target.value;
                setStartDate(val);
                updateBackendSettings({ start_date: val });
              }}
              className="border border-gray-300 rounded px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">End Date</label>
            <input 
              type="date" 
              value={endDate} 
              onChange={(e) => {
                const val = e.target.value;
                setEndDate(val);
                updateBackendSettings({ start_date: val });
              }}
              className="border border-gray-300 rounded px-3 py-1.5 text-sm"
            />
          </div>
          <button 
            onClick={() => setShowSettings(!showSettings)}
            className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded text-sm font-medium border border-gray-300 self-end transition"
          >
            ⚙️ Settings
          </button>
          <button 
            onClick={triggerOptimizationModel}
            className="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700 transition self-end text-sm font-medium"
          >
            Run Optimization Model
          </button>
        </div>
      </div>

      {showSettings && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-5 shadow-sm grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Min Call Interval</label>
            <input 
              type="number" 
              value={minCallInterval} 
              onChange={(e) => {
                const val = parseInt(e.target.value) || 0;
                setMinCallInterval(val);
                updateBackendSettings({ min_call_interval: val });
              }} 
              className="w-full border border-gray-300 rounded px-2.5 py-1 text-sm bg-white" 
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Max Teams / Week</label>
            <input 
              type="number" 
              value={maxTeamsPerWeek} 
              onChange={(e) => {
                const val = parseInt(e.target.value) || 0;
                setMaxTeamsPerWeek(val);
                updateBackendSettings({ max_teams_per_week: val });
              }} 
              className="w-full border border-gray-300 rounded px-2.5 py-1 text-sm bg-white" 
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Max Solve Time (s)</label>
            <input 
              type="number" 
              value={maxSolveTime} 
              onChange={(e) => {
                const val = parseInt(e.target.value) || 0;
                setMaxSolveTime(val);
                updateBackendSettings({ max_solve_time: val });
              }} 
              className="w-full border border-gray-300 rounded px-2.5 py-1 text-sm bg-white" 
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">AL Buffer (Before)</label>
            <input 
              type="number" 
              value={alCallBufferBefore} 
              onChange={(e) => {
                const val = parseInt(e.target.value) || 0;
                setAlCallBufferBefore(val);
                updateBackendSettings({ al_call_buffer_before: val });
              }} 
              className="w-full border border-gray-300 rounded px-2.5 py-1 text-sm bg-white" 
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">AL Buffer (After)</label>
            <input 
              type="number" 
              value={alCallBufferAfter} 
              onChange={(e) => {
                const val = parseInt(e.target.value) || 0;
                setAlCallBufferAfter(val);
                updateBackendSettings({ al_call_buffer_after: val });
              }} 
              className="w-full border border-gray-300 rounded px-2.5 py-1 text-sm bg-white" 
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Blockout Buffer (Before)</label>
            <input 
              type="number" 
              value={blockoutCallBufferBefore} 
              onChange={(e) => {
                const val = parseInt(e.target.value) || 0;
                setBlockoutCallBufferBefore(val);
                updateBackendSettings({ blockout_call_buffer_before: val });
              }} 
              className="w-full border border-gray-300 rounded px-2.5 py-1 text-sm bg-white" 
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Blockout Buffer (After)</label>
            <input 
              type="number" 
              value={blockoutCallBufferAfter} 
              onChange={(e) => {
                const val = parseInt(e.target.value) || 0;
                setBlockoutCallBufferAfter(val);
                updateBackendSettings({ blockout_call_buffer_after: val });
              }} 
              className="w-full border border-gray-300 rounded px-2.5 py-1 text-sm bg-white" 
            />
          </div>
        </div>
      )}

      <div>
        <div className="flex justify-between items-center mb-1">
          <h3 className="text-xs font-bold tracking-wider text-gray-400 mb-2">Team Requirements Configuration</h3>
          <button 
            onClick={handleAddTeamRow}
            className="mb-2 px-3 py-1 text-xs font-semibold text-white bg-gray-500 hover:bg-gray-700 rounded-md transition-colors"
          >
            + Add Team Row
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

            onCellValueChanged={onTeamCellValueChanged}
            stopEditingWhenCellsLoseFocus={true}
            onCellKeyDown={handleCellKeyDown}

            cellSelection={{ handle: { mode: 'fill' } }}
            enableFillHandle={true}
            undoRedoCellEditing={true}
            undoRedoCellEditingLimit={20}
            suppressRowClickSelection={true}
            enterNavigatesVertically={true}
            enterNavigatesVerticallyAfterEdit={true}
          />
        </div>
      </div>

      <div>
        <div className="flex justify-between items-center mb-1">
          <h3 className="text-xs font-bold tracking-wider text-gray-400 mb-2">Call Requirements Configuration</h3>
        </div>
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
            onCellValueChanged={onCallCellValueChanged}

            cellSelection={{ handle: { mode: 'fill' } }}
            enableFillHandle={true}
            undoRedoCellEditing={true}
            undoRedoCellEditingLimit={20}
            suppressRowClickSelection={true}
            enterNavigatesVertically={true}
            enterNavigatesVerticallyAfterEdit={true}
          />
        </div>
      </div>

      <div>
        <div className="flex justify-between items-center mb-1">
          <div className="flex items-center gap-4 mb-2">
            <h3 className="text-xs font-bold tracking-wider text-gray-400">Personnel Assignment & Call Roster</h3>
            
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
              className="mb-2 px-3 py-1 text-xs font-semibold text-white bg-gray-500 hover:bg-gray-700 rounded-md transition-colors"
            >
            + Add Person
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
            stopEditingWhenCellsLoseFocus={true}  
            alignedGrids={[topGridApi, middleGridApi].filter(Boolean)}

            onColumnResized={handleColumnResized}
            onCellKeyDown={handleCellKeyDown}

            cellSelection={{ handle: { mode: 'fill' } }}
            undoRedoCellEditing={true}  
            undoRedoCellEditingLimit={20}
            suppressRowClickSelection={true}
            enterNavigatesVertically={true}
            enterNavigatesVerticallyAfterEdit={true}
          />
        </div>
      </div>

      {isSolving && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-5 py-4 rounded-lg shadow-xl flex items-center gap-3 border border-slate-700 animate-fade-in max-w-sm">
          <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0"></div>
          <div>
            <p className="text-xs font-semibold text-blue-300">Solver Active</p>
            <p className="text-xs text-slate-200 mt-0.5">{solveMessage}</p>
          </div>
        </div>
      )}
    </div>
  );
}