// ARCA Spatial Studio - Frontend Client Logic

document.addEventListener('DOMContentLoaded', () => {
  // Navigation Tabs
  const tabBtnConverter = document.getElementById('tabBtnConverter');
  const tabBtnViewer = document.getElementById('tabBtnViewer');
  const viewConverter = document.getElementById('viewConverter');
  const viewViewer = document.getElementById('viewViewer');

  function switchTab(tabName) {
    if (tabName === 'converter') {
      tabBtnConverter.classList.add('active');
      tabBtnViewer.classList.remove('active');
      viewConverter.classList.remove('hidden');
      viewConverter.classList.add('active');
      viewViewer.classList.add('hidden');
      viewViewer.classList.remove('active');
      document.getElementById('vguide').style.display = "none";
    } else {
      tabBtnViewer.classList.add('active');
      tabBtnConverter.classList.remove('active');
      viewViewer.classList.remove('hidden');
      viewViewer.classList.add('active');
      viewConverter.classList.add('hidden');
      viewConverter.classList.remove('active');
      document.getElementById('vguide').style.display = "inline-flex";
      // Trigger map init / resize so viewport renders correctly
      setTimeout(() => {
        if (window.ARCA_VIEWER?.notifyVisible) {
          window.ARCA_VIEWER.notifyVisible();
        } else if (window.ARCA_VIEWER?.resize) {
          window.ARCA_VIEWER.resize();
        }
      }, 50);
      setTimeout(() => {
        if (window.ARCA_VIEWER?.resize) {
          window.ARCA_VIEWER.resize();
        }
      }, 300);
    }
  }

  tabBtnConverter?.addEventListener('click', () => switchTab('converter'));
  tabBtnViewer?.addEventListener('click', () => switchTab('viewer'));

  // Form & Dropzone Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const filePreview = document.getElementById('filePreview');
  const fileBadge = document.getElementById('fileBadge');
  const fileName = document.getElementById('fileName');
  const fileSize = document.getElementById('fileSize');
  const btnRemoveFile = document.getElementById('btnRemoveFile');
  const btnChangeFile = document.getElementById('btnChangeFile');
  const fileInfoArea = document.getElementById('fileInfoArea');
  const btnSubmit = document.getElementById('btnSubmit');
  const btnText = document.getElementById('btnText');
  const convertForm = document.getElementById('convertForm');

  // Inspection Elements
  const inspectBanner = document.getElementById('inspectBanner');
  const inspectBadge = document.getElementById('inspectBadge');
  const inspectCRS = document.getElementById('inspectCRS');
  const inspectBody = document.getElementById('inspectBody');
  const georefAccordion = document.getElementById('georefAccordion');

  // Input Fields for Georef
  const inputDatasetName = document.getElementById('datasetName');
  const inputAnchorLon = document.getElementById('anchorLon');
  const inputAnchorLat = document.getElementById('anchorLat');
  const inputCRS = document.getElementById('crs');
  const inputRotate = document.getElementById('rotate');
  const inputSourceUnit = document.getElementById('sourceUnit');

  // Metadata JSON Elements
  const enableMetadata = document.getElementById('enableMetadata');
  const metadataUploadArea = document.getElementById('metadataUploadArea');
  const metadataFileInput = document.getElementById('metadataFileInput');
  const btnRemoveMetadata = document.getElementById('btnRemoveMetadata');
  const metadataParsedStatus = document.getElementById('metadataParsedStatus');
  let selectedMetadataFile = null;

  // Results & Metrics Elements
  const resultCard = document.getElementById('resultCard');
  const emptyState = document.getElementById('emptyState');
  const statusBanner = document.getElementById('statusBanner');
  const metricsContainer = document.getElementById('metricsContainer');
  const statusTag = document.getElementById('statusTag');

  const resFormat = document.getElementById('resFormat');
  const resGeorefMethod = document.getElementById('resGeorefMethod');
  const resCRS = document.getElementById('resCRS');
  const resStoreys = document.getElementById('resStoreys');
  const resHeight = document.getElementById('resHeight');
  const resFootprint = document.getElementById('resFootprint');
  const resAnchor = document.getElementById('resAnchor');

  const btnDownloadGeoJSON = document.getElementById('btnDownloadGeoJSON');
  const btnDownloadGLB = document.getElementById('btnDownloadGLB');
  const btnOpenViewer = document.getElementById('btnOpenViewer');
  const btnDeleteResult = document.getElementById('btnDeleteResult');
  const logBox = document.getElementById('logBox');

  const progressContainer = document.getElementById('progressContainer');
  const progressStepTitle = document.getElementById('progressStepTitle');
  const progressPercent = document.getElementById('progressPercent');
  const progressTimer = document.getElementById('progressTimer');
  const progressBarFill = document.getElementById('progressBarFill');
  const liveLogBox = document.getElementById('liveLogBox');

  const historyBody = document.getElementById('historyBody');
  const btnRefreshHistory = document.getElementById('btnRefreshHistory');

  let selectedFile = null;
  let lastConvertedDataset = null;
  let currentInspectId = 0;
  let timerInterval = null;
  let timerStart = null;

  function startProgressTimer() {
    stopProgressTimer();
    timerStart = Date.now();
    if (progressTimer) {
      progressTimer.textContent = '00:00';
      progressTimer.style.display = 'inline';
    }
    timerInterval = setInterval(() => {
      if (!timerStart || !progressTimer) return;
      const elapsed = Math.floor((Date.now() - timerStart) / 1000);
      const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
      const ss = String(elapsed % 60).padStart(2, '0');
      progressTimer.textContent = `${mm}:${ss}`;
    }, 1000);
  }

  function stopProgressTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function resetResultCard() {
    lastConvertedDataset = null;
    stopProgressTimer();
    if (resultCard) resultCard.style.display = '';
    if (emptyState) emptyState.style.display = 'block';
    if (metricsContainer) metricsContainer.style.display = 'none';
    if (statusBanner) statusBanner.style.display = 'none';
    if (statusTag) statusTag.style.display = 'none';
    if (progressContainer) progressContainer.style.display = 'none';
    if (progressTimer) progressTimer.style.display = 'none';
    if (btnDeleteResult) btnDeleteResult.style.display = 'none';
    if (btnDownloadGeoJSON) btnDownloadGeoJSON.style.display = 'none';
    if (btnDownloadGLB) btnDownloadGLB.style.display = 'none';
    if (logBox) logBox.textContent = '-';
    if (liveLogBox) liveLogBox.textContent = '';
  }

  function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
  }

  async function inspectFileMetadata(file, inspectId) {
    inspectBanner.style.display = 'block';
    inspectBanner.className = 'inspect-banner loading';
    inspectBadge.textContent = 'Inspecting Metadata & Georeference...';
    inspectCRS.textContent = '...';
    inspectBody.innerHTML = 'Reading model headers and spatial entities...';

    const formData = new FormData();
    formData.append('file', file);
    if (enableMetadata && enableMetadata.checked && selectedMetadataFile) {
      formData.append('metadata', selectedMetadataFile);
    }

    try {
      const resp = await fetch('/api/inspect', {
        method: 'POST',
        body: formData
      });

      if (!resp.ok) {
        throw new Error('Failed to inspect file metadata');
      }

      const res = await resp.json();
      if (inspectId !== currentInspectId) return;

      const info = res.data || res;

      if (info.has_georef) {
        inspectBanner.className = 'inspect-banner success';
        if (info.method && info.method.startsWith('metadata_json')) {
          inspectBadge.textContent = '✓ Metadata JSON Georeference Detected';
        } else {
          inspectBadge.textContent = '✓ Automatic Georeferencing Detected';
        }
        inspectCRS.textContent = info.crs || 'CRS';
        
        let originText = '-';
        const lon = info.longitude !== undefined ? info.longitude : info.origin_lon;
        const lat = info.latitude !== undefined ? info.latitude : info.origin_lat;
        if (lon !== null && lat !== null && lon !== undefined && lat !== undefined) {
          originText = `${Number(lon).toFixed(6)}, ${Number(lat).toFixed(6)}`;
          inputAnchorLon.value = lon;
          inputAnchorLat.value = lat;
        }
        if (info.crs) {
          inputCRS.value = info.crs;
        }
        if (info.name && !inputDatasetName.value.trim()) {
          inputDatasetName.value = info.name;
        }
        const rot = info.rotate !== undefined ? info.rotate : info.rotation_deg;
        if (rot !== undefined && rot !== null) {
          inputRotate.value = rot;
        }
        const unit = info.unit || info.length_unit;
        if (unit) {
          const unitLower = unit.toLowerCase();
          if (unitLower === 'auto') inputSourceUnit.value = 'auto';
          else if (unitLower.includes('milli') || unitLower === 'mm') inputSourceUnit.value = 'mm';
          else if (unitLower.includes('centi') || unitLower === 'cm') inputSourceUnit.value = 'cm';
          else if (unitLower.includes('metre') || unitLower === 'meter' || unitLower === 'm') inputSourceUnit.value = 'm';
          else inputSourceUnit.value = 'auto';
        } else {
          inputSourceUnit.value = 'auto';
        }

        inspectBody.innerHTML = `
          <div class="inspect-grid">
            <div class="inspect-grid-item"><span>CRS:</span><strong>${info.crs || 'Projected'}</strong></div>
            <div class="inspect-grid-item"><span>Unit:</span><strong>${unit || 'Meters'}</strong></div>
            <div class="inspect-grid-item"><span>WGS84:</span><strong>${originText}</strong></div>
            <div class="inspect-grid-item"><span>Rotation:</span><strong>${rot ? rot + '°' : '0°'}</strong></div>
          </div>
          <div style="margin-top: 6px; font-size: 11px; color: #15803d;">
            Site parameters auto-filled. You can proceed directly to <strong>Start Conversion</strong>.
          </div>
        `;

        if (georefAccordion) georefAccordion.open = false;
      } else {
        inspectBanner.className = 'inspect-banner warning';
        inspectBadge.textContent = '⚠ No Internal Georeference Metadata';
        inspectCRS.textContent = 'Fallback';

        inspectBody.innerHTML = `
          <div>This model does not include georeference entities (CRS / site coordinates) inside the file.</div>
          <div style="margin-top: 4px; font-size: 11px; color: #a16207;">
            Default fallback coordinates will be used automatically, or fill site coordinates manually below.
          </div>
        `;

        if (georefAccordion) georefAccordion.open = true;
      }
    } catch (err) {
      if (inspectId !== currentInspectId) return;
      inspectBanner.className = 'inspect-banner warning';
      inspectBadge.textContent = 'Inspection Complete';
      inspectCRS.textContent = 'BIM';
      inspectBody.textContent = 'Model is ready to convert using standard settings.';
    } finally {
      if (inspectId === currentInspectId) {
        btnSubmit.disabled = false;
        btnSubmit.classList.remove('loading');
        btnText.textContent = 'Start Conversion';
      }
    }
  }

  function handleFileSelected(file) {
    if (!file) return;
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (ext !== '.ifc' && ext !== '.skp') {
      alert('Only .ifc or .skp files are supported');
      return;
    }

    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = formatBytes(file.size);
    
    fileBadge.textContent = ext.replace('.', '').toUpperCase();
    fileBadge.className = 'file-badge ' + (ext === '.ifc' ? 'ifc' : 'skp');

    dropzone.style.display = 'none';
    filePreview.classList.add('active');

    // Button stays disabled and in loading state until metadata inspection completes
    btnSubmit.disabled = true;
    btnSubmit.classList.add('loading');
    btnText.textContent = 'Inspecting Metadata...';

    // Run auto-inspection
    const inspectId = ++currentInspectId;
    inspectFileMetadata(file, inspectId);
  }

  function clearSelectedFile() {
    selectedFile = null;
    fileInput.value = '';
    dropzone.style.display = 'block';
    filePreview.classList.remove('active');
    inspectBanner.style.display = 'none';
    btnSubmit.disabled = true;
    btnSubmit.classList.remove('loading');
    btnText.textContent = 'Start Conversion';

    // Clear form overrides
    inputAnchorLon.value = '';
    inputAnchorLat.value = '';
    inputCRS.value = '';
    inputRotate.value = '';
    inputSourceUnit.value = 'auto';
    if (georefAccordion) georefAccordion.open = false;
  }

  // Dropzone drag & drop
  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  // Tombol ganti berkas / klik info berkas langsung membuka dialog file baru
  if (btnChangeFile) {
    btnChangeFile.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }
  if (fileInfoArea) {
    fileInfoArea.addEventListener('click', () => fileInput.click());
  }

  // Drag & drop berkas baru langsung ke atas area filePreview
  filePreview.addEventListener('dragover', (e) => {
    e.preventDefault();
    filePreview.style.borderColor = 'var(--text-primary)';
  });
  filePreview.addEventListener('dragleave', () => {
    filePreview.style.borderColor = '';
  });
  filePreview.addEventListener('drop', (e) => {
    e.preventDefault();
    filePreview.style.borderColor = '';
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  btnRemoveFile.addEventListener('click', clearSelectedFile);

  // Metadata JSON Controls
  if (enableMetadata) {
    enableMetadata.addEventListener('change', () => {
      if (enableMetadata.checked) {
        metadataUploadArea.style.display = 'block';
      } else {
        metadataUploadArea.style.display = 'none';
        selectedMetadataFile = null;
        if (metadataFileInput) metadataFileInput.value = '';
        if (btnRemoveMetadata) btnRemoveMetadata.style.display = 'none';
        if (metadataParsedStatus) {
          metadataParsedStatus.style.display = 'none';
          metadataParsedStatus.textContent = '';
        }
        if (selectedFile) {
          inspectFileMetadata(selectedFile, ++currentInspectId);
        }
      }
    });
  }

  if (metadataFileInput) {
    metadataFileInput.addEventListener('change', (e) => {
      if (!e.target.files || e.target.files.length === 0) return;
      const metaFile = e.target.files[0];
      selectedMetadataFile = metaFile;
      if (btnRemoveMetadata) btnRemoveMetadata.style.display = 'block';

      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const parsed = JSON.parse(ev.target.result);
          let name = parsed.name || parsed.building_name || '';
          let lon = parsed.longitude !== undefined ? parsed.longitude : (parsed.lon !== undefined ? parsed.lon : (parsed.anchor && parsed.anchor.lon));
          let lat = parsed.latitude !== undefined ? parsed.latitude : (parsed.lat !== undefined ? parsed.lat : (parsed.anchor && parsed.anchor.lat));
          let crs = parsed.crs || parsed.CRS || (parsed.georeference && parsed.georeference.crs_epsg ? `EPSG:${parsed.georeference.crs_epsg}` : '');
          let rot = parsed.rotate !== undefined ? parsed.rotate : (parsed.north_angle !== undefined ? parsed.north_angle : (parsed.rotation_deg !== undefined ? parsed.rotation_deg : (parsed.georeference && parsed.georeference.rotation_deg)));
          let unit = parsed.unit || parsed.length_unit || parsed.source_unit || '';

          if (parsed.type === 'FeatureCollection' && parsed.features && parsed.features.length > 0) {
            const feat = parsed.features[0];
            const props = feat.properties || {};
            name = name || props.name || props.building_name;
            crs = crs || props.crs || props.CRS;
            unit = unit || props.unit || props.length_unit || props.source_unit || '';
            if (feat.geometry && feat.geometry.type === 'Point' && Array.isArray(feat.geometry.coordinates)) {
              lon = feat.geometry.coordinates[0];
              lat = feat.geometry.coordinates[1];
            }
          } else if (parsed.type === 'Feature') {
            const props = parsed.properties || {};
            name = name || props.name || props.building_name;
            crs = crs || props.crs || props.CRS;
            unit = unit || props.unit || props.length_unit || props.source_unit || '';
            if (parsed.geometry && parsed.geometry.type === 'Point' && Array.isArray(parsed.geometry.coordinates)) {
              lon = parsed.geometry.coordinates[0];
              lat = parsed.geometry.coordinates[1];
            }
          }

          if (name && !inputDatasetName.value.trim()) inputDatasetName.value = name;
          if (lon !== undefined && lon !== null) inputAnchorLon.value = lon;
          if (lat !== undefined && lat !== null) inputAnchorLat.value = lat;
          if (crs) inputCRS.value = crs;
          if (rot !== undefined && rot !== null) inputRotate.value = rot;

          if (unit) {
            const unitLower = unit.toLowerCase();
            if (unitLower === 'auto') inputSourceUnit.value = 'auto';
            else if (unitLower.includes('milli') || unitLower === 'mm') inputSourceUnit.value = 'mm';
            else if (unitLower.includes('centi') || unitLower === 'cm') inputSourceUnit.value = 'cm';
            else if (unitLower.includes('metre') || unitLower === 'meter' || unitLower === 'm') inputSourceUnit.value = 'm';
            else inputSourceUnit.value = 'auto';
          } else {
            inputSourceUnit.value = 'auto';
          }

          if (metadataParsedStatus) {
            const dispLon = lon !== undefined && lon !== null ? Number(lon).toFixed(6) : '-';
            const dispLat = lat !== undefined && lat !== null ? Number(lat).toFixed(6) : '-';
            metadataParsedStatus.textContent = `✓ Loaded: ${metaFile.name} (Lon: ${dispLon}, Lat: ${dispLat}, CRS: ${crs || '-'}, Unit: ${inputSourceUnit.value})`;
            metadataParsedStatus.style.display = 'block';
          }
          if (georefAccordion) georefAccordion.open = true;
        } catch (err) {
          console.warn('Failed to parse metadata file locally', err);
        }

        if (selectedFile) {
          inspectFileMetadata(selectedFile, ++currentInspectId);
        }
      };
      reader.readAsText(metaFile);
    });
  }

  if (btnRemoveMetadata) {
    btnRemoveMetadata.addEventListener('click', () => {
      selectedMetadataFile = null;
      if (metadataFileInput) metadataFileInput.value = '';
      btnRemoveMetadata.style.display = 'none';
      if (metadataParsedStatus) {
        metadataParsedStatus.style.display = 'none';
        metadataParsedStatus.textContent = '';
      }
      if (selectedFile) {
        inspectFileMetadata(selectedFile, ++currentInspectId);
      }
    });
  }

  // Form submit
  convertForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    if (resultCard) resultCard.style.display = '';
    if (emptyState) emptyState.style.display = 'none';
    if (metricsContainer) metricsContainer.style.display = 'none';
    if (statusTag) statusTag.style.display = 'none';

    btnSubmit.disabled = true;
    btnSubmit.classList.add('loading');
    btnText.textContent = 'Processing Model...';
    statusBanner.className = 'status-banner';
    statusBanner.style.display = 'none';
    logBox.textContent = '';
    if (liveLogBox) liveLogBox.textContent = '';
    if (progressContainer) progressContainer.style.display = 'block';
    if (progressBarFill) progressBarFill.style.width = '0%';
    if (progressPercent) progressPercent.textContent = '0%';
    if (progressStepTitle) progressStepTitle.textContent = 'Starting conversion...';
    startProgressTimer();

    const formData = new FormData();
    formData.append('file', selectedFile);
    if (enableMetadata && enableMetadata.checked && selectedMetadataFile) {
      formData.append('metadata', selectedMetadataFile);
    }
    formData.append('dataset_name', inputDatasetName.value.trim());
    formData.append('generate', document.getElementById('generateMode').value);
    formData.append('anchor_lon', inputAnchorLon.value.trim());
    formData.append('anchor_lat', inputAnchorLat.value.trim());
    formData.append('crs', inputCRS.value.trim());
    formData.append('rotate', inputRotate.value.trim());
    formData.append('source_unit', inputSourceUnit.value);

    try {
      const resp = await fetch('/api/convert', {
        method: 'POST',
        body: formData
      });

      const initData = await resp.json();

      if (!resp.ok || !initData.success) {
        throw new Error(initData.error || 'Conversion failed');
      }

      const jobId = initData.job_id;

      await new Promise((resolve, reject) => {
        const es = new EventSource(`/api/jobs/${jobId}/events`);

        es.onmessage = (e) => {
          let event;
          try { event = JSON.parse(e.data); } catch { return; }

          if (event.type === 'progress') {
            const step = event.step != null ? event.step : null;
            const total = event.total ?? 5;
            const prefix = step != null ? `[${step}/${total}] ` : '';
            logBox.textContent += prefix + event.message + '\n';
            logBox.scrollTop = logBox.scrollHeight;
            if (liveLogBox) {
              liveLogBox.textContent += prefix + event.message + '\n';
              liveLogBox.scrollTop = liveLogBox.scrollHeight;
            }

            let pct = event.pct != null ? event.pct : null;
            if (pct == null && step != null) {
              pct = Math.round((step / total) * 100);
            }
            if (pct != null && progressBarFill) {
              progressBarFill.style.width = pct + '%';
              if (progressPercent) progressPercent.textContent = pct + '%';
            }

            let cleanMsg = event.message.trim();
            cleanMsg = cleanMsg.replace(/^\[SKP->IFC\]\s*/i, '');
            cleanMsg = cleanMsg.replace(/^\[\d+\/\d+\]\s*/, '');
            if (progressStepTitle) progressStepTitle.textContent = cleanMsg;
          } else if (event.type === 'error') {
            stopProgressTimer();
            es.close();
            if (progressContainer) progressContainer.style.display = 'none';
            reject(new Error(event.message || 'Conversion failed'));
          } else if (event.type === 'result') {
            stopProgressTimer();
            const data = event;
            lastConvertedDataset = data.dataset;
            if (progressBarFill) progressBarFill.style.width = '100%';
            if (progressPercent) progressPercent.textContent = '100%';
            if (progressStepTitle) progressStepTitle.textContent = 'Conversion complete!';
            setTimeout(() => { if (progressContainer) progressContainer.style.display = 'none'; }, 1200);

            if (resultCard) resultCard.style.display = '';
            emptyState.style.display = 'none';
            metricsContainer.style.display = 'block';
            statusTag.style.display = 'inline-block';
            if (btnDeleteResult) btnDeleteResult.style.display = 'inline-flex';

            statusBanner.className = 'status-banner success';
            statusBanner.textContent = `Model ${data.dataset} successfully converted in ${data.summary.elapsed_sec}s.`;
            statusBanner.style.display = 'block';

            resFormat.textContent = data.summary.format || 'BIM';
            resGeorefMethod.textContent = data.summary.georef_method === 'embedded' ? 'Automatic (File)' : 'Fallback Anchor';
            resCRS.textContent = data.summary.crs || 'EPSG:4326';
            resStoreys.textContent = data.summary.storeys || '-';
            resHeight.textContent = data.summary.height_m ? data.summary.height_m.toFixed(2) + ' m' : '-';
            resFootprint.textContent = data.summary.footprint_m2 ? data.summary.footprint_m2.toFixed(1) + ' m²' : '-';

            if (data.summary.anchor && data.summary.anchor[0] !== undefined) {
              resAnchor.textContent = `${Number(data.summary.anchor[0]).toFixed(6)}, ${Number(data.summary.anchor[1]).toFixed(6)}`;
            } else {
              resAnchor.textContent = '-';
            }

            if (data.files && data.files.geojson) {
              btnDownloadGeoJSON.href = data.files.geojson.url;
              btnDownloadGeoJSON.download = data.files.geojson.name || 'building.geojson';
              btnDownloadGeoJSON.style.display = 'inline-flex';
            } else {
              btnDownloadGeoJSON.style.display = 'none';
            }

            if (data.files && data.files.glb) {
              btnDownloadGLB.href = data.files.glb.url;
              btnDownloadGLB.download = data.files.glb.name || 'model_glb.zip';
              btnDownloadGLB.style.display = 'inline-flex';
            } else {
              btnDownloadGLB.style.display = 'none';
            }

            loadHistory();

            if (window.ARCA_VIEWER?.reloadDataset) {
              window.ARCA_VIEWER.reloadDataset(data.dataset);
            }

            // Reset input file form agar pengguna langsung bisa drop/pilih file baru tanpa klik close
            selectedFile = null;
            fileInput.value = '';
            dropzone.style.display = 'block';
            filePreview.classList.remove('active');
            inspectBanner.style.display = 'none';
            if (inputDatasetName) inputDatasetName.value = '';
          } else if (event.type === 'close') {
            es.close();
            resolve();
          }
        };

        es.onerror = () => {
          es.close();
          reject(new Error('SSE connection disconnected'));
        };
      });

    } catch (err) {
      if (resultCard) resultCard.style.display = '';
      if (!lastConvertedDataset && emptyState) {
        emptyState.style.display = 'block';
      }
      statusBanner.className = 'status-banner error';
      statusBanner.textContent = 'Processing failed: ' + err.message;
      statusBanner.style.display = 'block';
    } finally {
      stopProgressTimer();
      btnSubmit.classList.remove('loading');
      if (selectedFile) {
        btnSubmit.disabled = false;
        btnText.textContent = 'Start Conversion';
      } else {
        btnSubmit.disabled = true;
        btnText.textContent = 'Start Conversion';
      }
    }
  });

  // Delete dataset handler
  async function deleteDataset(datasetId) {
    if (!datasetId) return;
    if (!confirm(`Delete dataset "${datasetId}"? All GeoJSON and 3D model files will be permanently deleted.`)) {
      return;
    }
    try {
      const resp = await fetch(`/api/delete?dataset=${encodeURIComponent(datasetId)}`, {
        method: 'POST'
      });
      const res = await resp.json();
      if (res.success) {
        if (lastConvertedDataset === datasetId) {
          resetResultCard();
        }
        await loadHistory();
        if (window.ARCA_VIEWER?.reloadDataset) {
          window.ARCA_VIEWER.reloadDataset();
        }
      } else {
        alert('Delete failed: ' + (res.error || 'An error occurred'));
      }
    } catch (err) {
      alert('Failed to connect to server: ' + err.message);
    }
  }

  btnDeleteResult?.addEventListener('click', () => {
    if (lastConvertedDataset) {
      deleteDataset(lastConvertedDataset);
    }
  });

  // Open Viewer button click
  btnOpenViewer?.addEventListener('click', () => {
    switchTab('viewer');
    if (lastConvertedDataset && window.ARCA_VIEWER?.focusBuilding) {
      setTimeout(() => {
        window.ARCA_VIEWER.focusBuilding(lastConvertedDataset);
      }, 100);
    }
  });

  // Load history catalog
  async function loadHistory() {
    try {
      const resp = await fetch('/api/history');
      if (!resp.ok) return;
      const json = await resp.json();
      const list = json.datasets || [];

      if (list.length === 0) {
        historyBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">No converted models yet</td></tr>';
        return;
      }

      historyBody.innerHTML = list.map(item => {
        const bName = item.name || item.dataset;
        const safeName = encodeURIComponent(bName);
        return `
        <tr>
          <td>
            <a href="javascript:void(0)" class="history-item-link" data-dataset="${item.dataset}" style="font-weight:600; color:var(--text-primary); text-decoration:none;">
              ${item.name ? `${item.name} <span style="font-size:11px; font-weight:normal; color:var(--text-muted);">(${item.dataset})</span>` : item.dataset}
            </a>
            ${item.height_m ? `<div style="font-size:11px; color:var(--text-muted);">${item.height_m.toFixed(1)}m | ${item.footprint_m2 ? item.footprint_m2.toFixed(0)+'m²' : ''}</div>` : ''}
          </td>
          <td><span class="tag">${item.source_format || 'BIM'}</span></td>
          <td>${item.storeys || '-'}</td>
          <td style="font-size: 11px; color: var(--text-muted);">${item.timestamp || '-'}</td>
          <td style="text-align: right; white-space: nowrap;">
            ${item.has_geojson ? `<a href="/api/download?dataset=${item.dataset}&file=building.geojson&name=${safeName}" download="${bName}.geojson" class="btn-link" style="padding:2px 6px; font-size:11px;" title="Download GeoJSON">GeoJSON</a>` : ''}
            ${item.has_glb ? `<a href="/api/download?dataset=${item.dataset}&file=model_glb.zip&name=${safeName}" download="${bName}_glb.zip" class="btn-link" style="padding:2px 6px; font-size:11px;" title="Download GLB">GLB</a>` : ''}
            <button type="button" class="btn-link btn-view-model" data-dataset="${item.dataset}" style="padding:2px 6px; font-size:11px; color:var(--accent-blue);" title="View in 3D Viewer">View</button>
            <button type="button" class="btn-link btn-delete-model" data-dataset="${item.dataset}" style="padding:2px 6px; font-size:11px; color:#dc2626;" title="Delete model">Delete</button>
          </td>
        </tr>
      `;}).join('');

      // Attach click events for items
      document.querySelectorAll('.btn-view-model, .history-item-link').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const ds = e.currentTarget.getAttribute('data-dataset');
          switchTab('viewer');
          if (window.ARCA_VIEWER?.focusBuilding) {
            setTimeout(() => {
              window.ARCA_VIEWER.focusBuilding(ds);
            }, 100);
          }
        });
      });

      document.querySelectorAll('.btn-delete-model').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const ds = e.currentTarget.getAttribute('data-dataset');
          deleteDataset(ds);
        });
      });

    } catch (e) {
      console.warn('Failed to load catalog:', e);
    }
  }

  btnRefreshHistory?.addEventListener('click', loadHistory);
  loadHistory();
});