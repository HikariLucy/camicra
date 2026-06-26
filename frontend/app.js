const API_BASE_URL = '/api';

// --- Fetch Interceptor para JWT ---
const originalFetch = window.fetch;
window.fetch = async function() {
    let [resource, config] = arguments;
    
    if (typeof resource === 'string' && resource.startsWith(API_BASE_URL)) {
        const token = localStorage.getItem('jwt_token');
        if (!config) config = {};
        if (!config.headers) config.headers = {};
        
        if (token) {
            if (config.headers instanceof Headers) {
                config.headers.append('Authorization', `Bearer ${token}`);
            } else if (Array.isArray(config.headers)) {
                config.headers.push(['Authorization', `Bearer ${token}`]);
            } else {
                config.headers['Authorization'] = `Bearer ${token}`;
            }
        }
    }
    
    const response = await originalFetch(resource, config);
    
    if (response.status === 401 && !resource.endsWith('/login')) {
        localStorage.removeItem('jwt_token');
        window.location.href = 'login.html';
    }
    
    return response;
};

let chartTematicasInstance = null;
let chartNivelesInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    cargarInventario();
    initInventarioForm();
    initImportacion();
    cargarMateriales();
    initMaterialesForm();
    initPrestamosForm();
    cargarPrestamos();
    initCalendar();
    initIAForm();
    initEventoIAForm();
    verificarAlertas();
    
    // Configurar toggle del popup de alertas
    const btnAlertas = document.getElementById('btn-alertas');
    const popupAlertas = document.getElementById('popup-alertas');
    if (btnAlertas && popupAlertas) {
        btnAlertas.addEventListener('click', (e) => {
            e.stopPropagation();
            popupAlertas.classList.toggle('hidden');
        });
        
        // Cerrar al hacer clic fuera
        document.addEventListener('click', (e) => {
            if (!popupAlertas.contains(e.target) && !btnAlertas.contains(e.target)) {
                popupAlertas.classList.add('hidden');
            }
        });
    }
});
function initTabs() {
    const navBtns = document.querySelectorAll('.nav-btn');
    const contents = document.querySelectorAll('.tab-content');

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remover estado 'activo' de todos los botones
            navBtns.forEach(b => {
                b.classList.remove('bg-blue-800', 'text-white');
                b.classList.add('text-blue-100');
            });
            
            // Ocultar todas las secciones
            contents.forEach(c => {
                c.classList.remove('block');
                c.classList.add('hidden');
            });

            // Activar el botón presionado
            btn.classList.remove('text-blue-100');
            btn.classList.add('bg-blue-800', 'text-white');
            
            // Mostrar la sección correspondiente
            const targetId = btn.getAttribute('data-target');
            const targetSection = document.getElementById(targetId);
            targetSection.classList.remove('hidden');
            targetSection.classList.add('block');
            
            // Cargar estadísticas si se abre esa pestaña
            if (targetId === 'tab-estadisticas') {
                cargarEstadisticas();
            }
            
            // Cambiar título de pestaña
            const titleMap = {
                'tab-inventario': 'Inventario - Cami CRA',
                'tab-eventos': 'Eventos - Cami CRA',
                'tab-materiales': 'Materiales - Cami CRA',
                'tab-prestamos': 'Préstamos - Cami CRA',
                'tab-estadisticas': 'Estadísticas - Cami CRA',
                'tab-ia': '✨ Asistente IA - Cami CRA',
                'tab-evento-ia': '💡 Crear Evento - Cami CRA'
            };
            document.title = titleMap[targetId] || 'Cami CRA - Asistente de Biblioteca';
        });
    });
}

// Cargar Inventario desde la API y poblar la tabla estilizada
async function cargarInventario() {
    try {
        const response = await fetch(`${API_BASE_URL}/inventario`);
        if (!response.ok) throw new Error('Error al obtener inventario');
        
        const libros = await response.json();
        const tbody = document.querySelector('#tabla-inventario tbody');
        tbody.innerHTML = '';
        
        if (libros.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500 text-sm">No hay libros en el inventario.</td></tr>';
            return;
        }

        libros.forEach(libro => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-gray-50 transition'; // Tailwind hover
            tr.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${libro.id}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <img src="${libro.foto_blob ? 'data:image/jpeg;base64,' + libro.foto_blob : 'https://via.placeholder.com/50x70?text=Sin+Foto'}" alt="Portada" class="w-12 h-16 object-cover rounded shadow-sm border border-gray-200">
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${libro.titulo}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${libro.autor}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        ${libro.nivel}
                    </span>
                </td>
                <td class="px-6 py-4 text-sm text-gray-600">${libro.tematicas}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-semibold">${libro.estanteria}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error('Error:', error);
        document.querySelector('#tabla-inventario tbody').innerHTML = `<tr><td colspan="7" class="px-6 py-4 text-center text-red-500 text-sm font-medium">Error al cargar los datos: ${error.message}</td></tr>`;
    }
}

// Manejo del formulario de Inventario y Autocompletado
function initInventarioForm() {
    const form = document.getElementById('form-inventario');
    const isbnInput = document.getElementById('isbn');
    const tituloInput = document.getElementById('titulo');
    const autorInput = document.getElementById('autor');

    // Autocompletado Mágico con Backend
    isbnInput.addEventListener('blur', async () => {
        const isbn = isbnInput.value.trim().replace(/-/g, '');
        if (!isbn) return;

        try {
            const response = await fetch(`${API_BASE_URL}/libros/buscar-isbn/${isbn}`);
            if (!response.ok) throw new Error('Error buscando ISBN');
            const data = await response.json();

            if (data.titulo) {
                tituloInput.value = data.titulo;
                autorInput.value = data.autor;
                
                if (data.foto_blob) {
                    form.dataset.fotoBlob = data.foto_blob;
                } else {
                    form.dataset.fotoBlob = "";
                }

                // Resaltar visualmente para indicar éxito
                tituloInput.classList.add('bg-blue-50');
                autorInput.classList.add('bg-blue-50');
                setTimeout(() => {
                    tituloInput.classList.remove('bg-blue-50');
                    autorInput.classList.remove('bg-blue-50');
                }, 1000);
            }
        } catch (error) {
            console.error('Error al autocompletar ISBN:', error);
        }
    });

    // Guardar Libro
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const nuevoLibro = {
            titulo: tituloInput.value.trim(),
            autor: autorInput.value.trim(),
            nivel: document.getElementById('nivelLibro').value.trim(),
            tematicas: document.getElementById('tematicas').value.trim(),
            estanteria: document.getElementById('estanteriaLibro').value.trim(),
            isbn: isbnInput.value.trim().replace(/-/g, ''),
            foto_blob: form.dataset.fotoBlob || null
        };

        try {
            const response = await fetch(`${API_BASE_URL}/inventario`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(nuevoLibro)
            });

            if (!response.ok) throw new Error('Error al guardar el libro');

            // Limpiar formulario y recargar tabla
            form.reset();
            cargarInventario();
            alert('¡Libro guardado exitosamente en el inventario!');
        } catch (error) {
            alert('Error al guardar el libro: ' + error.message);
        }
    });
}

// Manejo de Importación Masiva (CSV / Excel)
function initImportacion() {
    const formImportar = document.getElementById('form-importar');
    const importLoader = document.getElementById('import-loader');

    formImportar.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const fileInput = document.getElementById('fileImport');
        if (!fileInput.files.length) return;

        // Mostrar spinner/mensaje
        importLoader.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        try {
            const response = await fetch(`${API_BASE_URL}/inventario/importar`, {
                method: 'POST',
                body: formData // Fetch detecta automáticamente que es multipart/form-data
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Error en la importación');
            }

            const data = await response.json();
            alert(`¡Éxito! ${data.cantidad} libros importados mágicamente.`);
            
            // Limpiar y recargar tabla
            formImportar.reset();
            cargarInventario();
        } catch (error) {
            alert('Error al importar: ' + error.message);
        } finally {
            // Ocultar spinner/mensaje
            importLoader.classList.add('hidden');
        }
    });
}


// Variable global para el calendario
let calendarInstance = null;

// Inicializar Calendario de Eventos con FullCalendar
async function initCalendar() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;

    try {
        const [eventosRes, feriadosRes] = await Promise.all([
            fetch(`${API_BASE_URL}/eventos`),
            fetch(`${API_BASE_URL}/feriados`)
        ]);
        
        if (!eventosRes.ok) throw new Error('Error al obtener eventos');
        if (!feriadosRes.ok) throw new Error('Error al obtener feriados');
        
        const eventosData = await eventosRes.json();
        const feriadosData = await feriadosRes.json();
        
        // Mapear los datos de la API al formato de FullCalendar
        const eventosMapeados = eventosData.map(evento => ({
            id: evento.id,
            title: evento.nombre_evento,
            start: evento.fecha,
            description: evento.objetivo,
            color: '#1e3a8a', // Azul marino institucional
            isHoliday: false
        }));

        // Combinar eventos y feriados
        const todosLosEventos = [...eventosMapeados, ...feriadosData];

        calendarInstance = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: 'es',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,dayGridWeek'
            },
            events: todosLosEventos,
            eventClick: function(info) {
                const modal = document.getElementById('evento-modal');
                const overlay = document.getElementById('evento-modal-overlay');
                const title = document.getElementById('evento-modal-title');
                const date = document.getElementById('evento-modal-date');
                const desc = document.getElementById('evento-modal-desc');
                const deleteBtn = document.getElementById('evento-modal-delete');

                title.textContent = info.event.title;
                date.textContent = info.event.startStr;
                desc.textContent = info.event.extendedProps.description || 'Sin descripción adicional.';
                
                // Si es un feriado, ocultar el botón eliminar
                if (info.event.extendedProps.isHoliday) {
                    deleteBtn.classList.add('hidden');
                    deleteBtn.onclick = null;
                } else {
                    deleteBtn.classList.remove('hidden');
                    deleteBtn.onclick = () => {
                        eliminarEvento(info.event.id);
                        modal.classList.add('hidden');
                        overlay.classList.add('hidden');
                    };
                }

                // Mostrar el modal
                modal.classList.remove('hidden');
                overlay.classList.remove('hidden');

                // Lógica de cierre del modal
                const closeBtn = document.getElementById('evento-modal-close');
                const cerrarModal = () => {
                    modal.classList.add('hidden');
                    overlay.classList.add('hidden');
                };
                closeBtn.onclick = cerrarModal;
                overlay.onclick = cerrarModal;
            },
            buttonText: {
                today: 'Hoy',
                month: 'Mes',
                week: 'Semana'
            }
        });

        // Asegurarse de que el calendario se renderice bien al cambiar de pestaña
        const tabEventosBtn = document.querySelector('[data-target="tab-eventos"]');
        if (tabEventosBtn) {
            tabEventosBtn.addEventListener('click', () => {
                setTimeout(() => {
                    calendarInstance.render();
                }, 100);
            });
        }

        calendarInstance.render();

    } catch (error) {
        console.error('Error:', error);
        calendarEl.innerHTML = `<div class="p-4 text-red-500 text-center font-medium">Error al cargar el calendario: ${error.message}</div>`;
    }
}

async function eliminarEvento(id) {
    if(!confirm("¿Estás seguro de que deseas eliminar este evento?")) return;
    try {
        const response = await fetch(`${API_BASE_URL}/eventos/${id}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error('Error al eliminar evento');
        
        // Remover el evento del calendario en vivo para no tener que recargar todo
        const event = calendarInstance.getEventById(id);
        if(event) {
            event.remove();
        }
    } catch (error) {
        alert("Error: " + error.message);
    }
}

// Manejo del formulario de Inteligencia Artificial
function initIAForm() {
    const form = document.getElementById('form-ia');
    const loader = document.getElementById('ia-loader');
    const resultContainer = document.getElementById('ia-result');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const nombreAlumno = document.getElementById('nombreAlumno').value.trim();
        const librosInput = document.getElementById('librosFavoritos').value;
        const librosFavoritos = librosInput.split(',').map(libro => libro.trim()).filter(l => l !== '');

        if (!nombreAlumno || librosFavoritos.length === 0) {
            alert('Por favor, ingresa el nombre del alumno y al menos un libro favorito.');
            return;
        }

        // Mostrar Loader y Ocultar Resultado anterior (usando flex/hidden de Tailwind)
        loader.classList.remove('hidden');
        loader.classList.add('flex');
        resultContainer.classList.add('hidden');
        resultContainer.innerHTML = '';

        try {
            const response = await fetch(`${API_BASE_URL}/recomendacion-ia`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    nombre_alumno: nombreAlumno,
                    libros_favoritos: librosFavoritos
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Error en la solicitud a la IA');
            }

            const data = await response.json();
            
            // Renderizar Markdown usando Marked.js
            const htmlContent = marked.parse(data.respuesta);
            
            resultContainer.innerHTML = htmlContent;
            resultContainer.classList.remove('hidden');

        } catch (error) {
            console.error('Error al generar recomendación:', error);
            resultContainer.innerHTML = `<div class="bg-red-50 border-l-4 border-red-500 p-4 rounded-md text-red-700">
                <p class="font-bold">❌ Error en la generación</p>
                <p>${error.message}</p>
            </div>`;
            resultContainer.classList.remove('hidden');
        } finally {
            // Ocultar Loader
            loader.classList.remove('flex');
            loader.classList.add('hidden');
        }
    });
}

// Manejo del formulario de Planificador de Eventos IA
function initEventoIAForm() {
    const form = document.getElementById('form-evento-ia');
    if(!form) return;
    const loader = document.getElementById('evento-ia-loader');
    const resultContainer = document.getElementById('evento-ia-result');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const tipoActividad = document.getElementById('tipoActividad').value.trim();
        const objetivoEvento = document.getElementById('objetivoEvento').value.trim();

        if (!tipoActividad || !objetivoEvento) {
            alert('Por favor, ingresa el tipo de actividad y el objetivo.');
            return;
        }

        loader.classList.remove('hidden');
        loader.classList.add('flex');
        resultContainer.classList.add('hidden');
        resultContainer.innerHTML = '';

        try {
            const response = await fetch(`${API_BASE_URL}/generar-evento-ia`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tipo_actividad: tipoActividad,
                    objetivo: objetivoEvento
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Error en la solicitud a la IA');
            }

            const data = await response.json();
            
            const htmlContent = marked.parse(data.respuesta);
            
            resultContainer.innerHTML = htmlContent;
            resultContainer.classList.remove('hidden');

        } catch (error) {
            console.error('Error al generar evento:', error);
            resultContainer.innerHTML = `<div class="bg-red-50 border-l-4 border-red-500 p-4 rounded-md text-red-700">
                <p class="font-bold">❌ Error en la generación</p>
                <p>${error.message}</p>
            </div>`;
            resultContainer.classList.remove('hidden');
        } finally {
            loader.classList.remove('flex');
            loader.classList.add('hidden');
        }
    });
}

// --- Material Pedagógico ---

async function cargarMateriales() {
    try {
        const response = await fetch(`${API_BASE_URL}/materiales`);
        if (!response.ok) throw new Error('Error al cargar materiales');
        
        const materiales = await response.json();
        const grid = document.getElementById('grid-materiales');
        if(!grid) return;
        grid.innerHTML = '';
        
        if (materiales.length === 0) {
            grid.innerHTML = '<div class="col-span-full text-center text-gray-500 py-8">No hay materiales registrados aún.</div>';
            return;
        }

        materiales.forEach(mat => {
            const imgSrc = mat.foto ? mat.foto : 'https://via.placeholder.com/300x200?text=Sin+Imagen';
            const card = document.createElement('div');
            card.className = 'bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition';
            card.innerHTML = `
                <img src="${imgSrc}" alt="${mat.nombre}" class="w-full h-48 object-cover">
                <div class="p-4">
                    <h4 class="text-lg font-bold text-gray-900 mb-1">${mat.nombre}</h4>
                    <p class="text-sm text-gray-600 line-clamp-3">${mat.descripcion}</p>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (error) {
        console.error('Error:', error);
        const grid = document.getElementById('grid-materiales');
        if(grid) grid.innerHTML = `<div class="col-span-full text-red-500 text-center py-4">Error al cargar materiales: ${error.message}</div>`;
    }
}

function initMaterialesForm() {
    const form = document.getElementById('form-material');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const nombre = document.getElementById('nombreMaterial').value.trim();
        const descripcion = document.getElementById('descMaterial').value.trim();
        const fotoInput = document.getElementById('fotoMaterial');
        
        const formData = new FormData();
        formData.append('nombre', nombre);
        formData.append('descripcion', descripcion);
        if (fotoInput.files.length > 0) {
            formData.append('foto', fotoInput.files[0]);
        }

        try {
            const response = await fetch(`${API_BASE_URL}/materiales`, {
                method: 'POST',
                body: formData // Fetch gestiona el boundary de multipart/form-data automáticamente
            });

            if (!response.ok) throw new Error('Error al guardar el material');

            alert('¡Material pedagógico guardado exitosamente!');
            form.reset();
            cargarMateriales(); // recargar la cuadrícula
        } catch (error) {
            alert('Error al guardar: ' + error.message);
        }
    });
}

// --- Préstamos y Notificaciones ---

async function cargarPrestamos() {
    try {
        const response = await fetch(`${API_BASE_URL}/prestamos/activos`);
        if (!response.ok) throw new Error('Error al cargar préstamos');
        
        const prestamos = await response.json();
        const tbody = document.getElementById('tbody-prestamos');
        const panelNotificaciones = document.getElementById('panel-notificaciones');
        
        if(!tbody || !panelNotificaciones) return;
        
        tbody.innerHTML = '';
        panelNotificaciones.innerHTML = '';
        
        const hoy = new Date();
        hoy.setHours(0,0,0,0); // Normalizar a medianoche para evitar falsos positivos por hora

        if (prestamos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-500">No hay préstamos activos.</td></tr>';
            return;
        }

        prestamos.forEach(p => {
            // Lógica de Notificaciones
            const fechaDev = new Date(p.fecha_devolucion + 'T00:00:00'); // Tratar como local
            const diffTime = fechaDev - hoy;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            let colorClase = 'text-gray-900'; // Color default
            
            if (diffDays < 0) {
                // Atrasado (Rojo)
                colorClase = 'text-red-600 font-bold';
                panelNotificaciones.innerHTML += `
                    <div class="bg-red-50 border-l-4 border-red-500 p-4 rounded-md shadow-sm">
                        <div class="flex">
                            <div class="flex-shrink-0"><span class="text-red-500">❌</span></div>
                            <div class="ml-3">
                                <p class="text-sm text-red-700 font-bold">¡Atrasado!</p>
                                <p class="text-sm text-red-600"><strong>${p.nombre_alumno}</strong> no ha devuelto <em>${p.nombre_item}</em> (Venció el ${p.fecha_devolucion}).</p>
                            </div>
                        </div>
                    </div>`;
            } else if (diffDays <= 2) {
                // Vence pronto (Amarillo)
                panelNotificaciones.innerHTML += `
                    <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-md shadow-sm">
                        <div class="flex">
                            <div class="flex-shrink-0"><span class="text-yellow-400">⚠️</span></div>
                            <div class="ml-3">
                                <p class="text-sm text-yellow-700 font-bold">Próximo a Vencer</p>
                                <p class="text-sm text-yellow-600">El préstamo de <em>${p.nombre_item}</em> por <strong>${p.nombre_alumno}</strong> vence en ${diffDays} día(s).</p>
                            </div>
                        </div>
                    </div>`;
            }
            
            // Fila de la tabla
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium ${colorClase}">
                    <span class="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded mr-2">${p.tipo_item}</span> ${p.nombre_item}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-semibold">${p.estanteria || '-'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-blue-600 font-bold hover:underline cursor-pointer" onclick="abrirCarnetLector('${p.nombre_alumno}')" title="Ver Perfil del Alumno">${p.nombre_alumno}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-semibold">${p.curso}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${p.fecha_prestamo}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-bold ${colorClase}">${p.fecha_devolucion}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button onclick="devolverPrestamo(${p.id})" class="text-green-600 hover:text-green-900 bg-green-50 hover:bg-green-100 px-3 py-1 rounded-md transition border border-green-200 shadow-sm">
                        ✓ Marcar como Devuelto
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        // Verificar alerta global al cargar préstamos
        verificarAlertas();
        
    } catch (error) {
        console.error('Error al cargar préstamos:', error);
    }
}

function initPrestamosForm() {
    const form = document.getElementById('form-prestamo');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Fecha actual en formato YYYY-MM-DD
        const hoy = new Date().toISOString().split('T')[0];
        
        const nuevoPrestamo = {
            tipo_item: document.getElementById('tipoItem').value,
            nombre_item: document.getElementById('nombreItemPrestamo').value.trim(),
            nombre_alumno: document.getElementById('nombreAlumno').value.trim(),
            curso: document.getElementById('cursoAlumno').value.trim(),
            fecha_prestamo: hoy,
            fecha_devolucion: document.getElementById('fechaDevolucion').value
        };

        try {
            const response = await fetch(`${API_BASE_URL}/prestamos`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(nuevoPrestamo)
            });

            if (!response.ok) throw new Error('Error al registrar el préstamo');

            form.reset();
            cargarPrestamos(); // Refrescar tabla y alertas
        } catch (error) {
            alert('Error al registrar: ' + error.message);
        }
    });
}

async function devolverPrestamo(id) {
    if (!confirm('¿Estás seguro de que este ítem fue devuelto?')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/prestamos/${id}/devolver`, {
            method: 'PUT'
        });

        if (!response.ok) throw new Error('Error al marcar devolución');
        
        cargarPrestamos(); // Refrescar vista, se limpiarán las alertas si era el último
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// --- Notificaciones Globales ---
async function verificarAlertas() {
    try {
        const response = await fetch(`${API_BASE_URL}/prestamos/alerta-pendiente`);
        if (!response.ok) return;
        const data = await response.json();
        
        const indicador = document.getElementById('indicador-alerta');
        const btnAlertas = document.getElementById('btn-alertas');
        const listaAlertas = document.getElementById('lista-alertas');
        
        if (indicador && btnAlertas && listaAlertas) {
            if (data.tiene_pendientes) {
                indicador.classList.remove('hidden');
                btnAlertas.classList.remove('text-gray-300');
                btnAlertas.classList.add('text-yellow-400');
                
                listaAlertas.innerHTML = '';
                data.detalles.forEach(a => {
                    listaAlertas.innerHTML += `
                        <div class="p-2 border-b border-gray-100 last:border-0 hover:bg-gray-50">
                            <p class="text-xs text-red-600 font-semibold mb-1">¡Atrasado! (Venció: ${a.fecha_devolucion})</p>
                            <p class="text-sm text-gray-800"><strong>${a.nombre_alumno}</strong></p>
                            <p class="text-xs text-gray-600">${a.nombre_item}</p>
                        </div>
                    `;
                });
            } else {
                indicador.classList.add('hidden');
                btnAlertas.classList.remove('text-yellow-400');
                btnAlertas.classList.add('text-gray-300');
                listaAlertas.innerHTML = '<div class="p-4 text-center text-sm text-gray-500">No hay préstamos atrasados.</div>';
            }
        }
    } catch (error) {
        console.error('Error al verificar alertas:', error);
    }
}

// --- Dashboard Estadísticas ---

async function cargarEstadisticas() {
    try {
        const response = await fetch(`${API_BASE_URL}/estadisticas`);
        if (!response.ok) throw new Error('Error al cargar estadísticas');
        
        const data = await response.json();
        
        // 1. Actualizar Tarjetas de Resumen
        document.getElementById('stat-libros').innerText = data.totales.libros;
        document.getElementById('stat-materiales').innerText = data.totales.materiales;
        document.getElementById('stat-prestamos').innerText = data.totales.prestamos_activos;
        
        // 2. Gráfico de Temáticas (Barras)
        const ctxTematicas = document.getElementById('chartTematicas');
        if (ctxTematicas) {
            if (chartTematicasInstance) chartTematicasInstance.destroy();
            
            const labelsTematicas = Object.keys(data.tematicas);
            const valuesTematicas = Object.values(data.tematicas);
            
            chartTematicasInstance = new Chart(ctxTematicas, {
                type: 'bar',
                data: {
                    labels: labelsTematicas,
                    datasets: [{
                        label: 'Libros por Temática',
                        data: valuesTematicas,
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgb(59, 130, 246)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
                }
            });
        }
        
        // 3. Gráfico de Niveles (Circular)
        const ctxNiveles = document.getElementById('chartNiveles');
        if (ctxNiveles) {
            if (chartNivelesInstance) chartNivelesInstance.destroy();
            
            const labelsNiveles = Object.keys(data.niveles);
            const valuesNiveles = Object.values(data.niveles);
            
            chartNivelesInstance = new Chart(ctxNiveles, {
                type: 'doughnut',
                data: {
                    labels: labelsNiveles,
                    datasets: [{
                        data: valuesNiveles,
                        backgroundColor: [
                            'rgba(239, 68, 68, 0.7)',
                            'rgba(16, 185, 129, 0.7)',
                            'rgba(245, 158, 11, 0.7)',
                            'rgba(139, 92, 246, 0.7)',
                            'rgba(59, 130, 246, 0.7)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            });
        }
        
        // 4. Cargar Recomendación Diaria IA
        cargarRecomendacionDiaria();
        
    } catch (error) {
        console.error('Error al cargar estadísticas:', error);
    }
}

async function cargarRecomendacionDiaria() {
    const btn = document.getElementById('btn-refrescar-recomendacion');
    const loader = document.getElementById('recomendacion-loader');
    const contenido = document.getElementById('recomendacion-contenido');
    const elTitulo = document.getElementById('rec-titulo');
    const elAutor = document.getElementById('rec-autor');
    const elMensaje = document.getElementById('rec-mensaje');

    if(!btn || !loader || !contenido) return;

    btn.disabled = true;
    btn.classList.add('opacity-50', 'cursor-not-allowed');
    loader.classList.remove('hidden');
    contenido.classList.add('hidden');

    try {
        const response = await fetch(`${API_BASE_URL}/recomendacion-diaria`);
        if (!response.ok) throw new Error('Error al generar la recomendación');
        
        const data = await response.json();
        
        elTitulo.textContent = data.titulo || 'Sin título';
        elAutor.textContent = data.autor || 'Desconocido';
        elMensaje.textContent = data.mensaje || 'Te recomendamos explorar la biblioteca para descubrir mundos nuevos.';
        
        loader.classList.add('hidden');
        contenido.classList.remove('hidden');
    } catch (error) {
        console.error('Error en recomendación diaria:', error);
        loader.classList.add('hidden');
        contenido.classList.remove('hidden');
        elTitulo.textContent = 'Aviso';
        elAutor.textContent = 'Cami CRA';
        elMensaje.textContent = 'Hubo un inconveniente conectando con la IA. ¡Pero nuestra biblioteca siempre tiene sorpresas esperándote en las estanterías!';
    } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}

// --- Módulo: Carnet de Lector (Perfil del Alumno) ---

let chartCarnetInstance = null;

async function abrirCarnetLector(nombreAlumno) {
    try {
        const response = await fetch(`${API_BASE_URL}/alumnos/${encodeURIComponent(nombreAlumno)}/historial`);
        if (!response.ok) throw new Error('Error al cargar el historial del alumno');
        
        const data = await response.json();
        
        // 1. Rellenar Datos Básicos
        document.getElementById('carnet-nombre').textContent = data.alumno;
        
        // 2. Construir Historial (lista)
        const lista = document.getElementById('lista-historial');
        lista.innerHTML = '';
        if(data.prestamos.length === 0) {
            lista.innerHTML = '<p class="text-gray-500 italic">No hay registros de lectura para este alumno.</p>';
        } else {
            data.prestamos.forEach(p => {
                const esActivo = p.estado === 'Activo';
                const bgItem = esActivo ? 'bg-blue-50 border border-blue-100' : 'bg-gray-50 border border-gray-200';
                const icon = p.tipo_item === 'Libro' ? '📖' : '🧩';
                const estadoBadge = esActivo 
                    ? '<span class="px-2 py-1 text-xs font-bold rounded-full bg-yellow-100 text-yellow-800">Leyendo</span>'
                    : '<span class="px-2 py-1 text-xs font-bold rounded-full bg-green-100 text-green-800">Devuelto</span>';
                
                lista.innerHTML += `
                    <div class="p-3 rounded-lg flex items-center justify-between ${bgItem}">
                        <div class="flex items-center gap-3">
                            <div class="text-xl">${icon}</div>
                            <div>
                                <h4 class="text-sm font-bold text-gray-800">${p.nombre_item}</h4>
                                <p class="text-xs text-gray-500">${p.fecha_prestamo} ${p.fecha_devolucion ? '→ ' + p.fecha_devolucion : ''}</p>
                            </div>
                        </div>
                        <div>
                            ${estadoBadge}
                        </div>
                    </div>
                `;
            });
        }
        
        // 3. Gráfico de Temáticas (Chart.js)
        const ctx = document.getElementById('chartCarnet');
        if (ctx) {
            if (chartCarnetInstance) chartCarnetInstance.destroy();
            
            const labels = Object.keys(data.tematicas);
            const values = Object.values(data.tematicas);
            
            if(labels.length > 0) {
                ctx.parentElement.style.display = 'flex';
                chartCarnetInstance = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: [
                                '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#6366f1'
                            ],
                            borderWidth: 2,
                            borderColor: '#ffffff'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { 
                            legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } }
                        }
                    }
                });
            } else {
                ctx.parentElement.style.display = 'none'; // Ocultar si no hay datos
            }
        }
        
        // Configurar botón PDF
        const btnPdf = document.getElementById('btn-pdf-historial');
        btnPdf.onclick = () => generarPDFHistorial(data);

        // Mostrar Modal
        const modal = document.getElementById('modal-carnet-lector');
        modal.classList.remove('hidden');
        
        // Configurar cierre
        document.getElementById('btn-cerrar-carnet').onclick = () => {
            modal.classList.add('hidden');
        };

    } catch (error) {
        console.error('Error abriendo carnet:', error);
        alert('Hubo un error al cargar los datos del alumno.');
    }
}

function generarPDFHistorial(data) {
    if(!window.jspdf) {
        alert("La librería PDF no está cargada. Por favor recarga la página.");
        return;
    }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    
    // Encabezado
    doc.setFillColor(30, 58, 138); // Azul institucional
    doc.rect(0, 0, 210, 40, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(22);
    doc.text("Carnet de Lector", 105, 20, null, null, "center");
    doc.setFontSize(12);
    doc.text(`Alumno: ${data.alumno}`, 105, 30, null, null, "center");
    
    // Historial
    doc.setTextColor(0, 0, 0);
    doc.setFontSize(16);
    doc.text("Historial de Préstamos", 20, 55);
    
    doc.setFontSize(10);
    let yPos = 65;
    
    if(data.prestamos.length === 0) {
        doc.text("No hay registros.", 20, yPos);
    } else {
        data.prestamos.forEach((p, index) => {
            if(yPos > 270) {
                doc.addPage();
                yPos = 20;
            }
            doc.text(`${index + 1}. [${p.estado}] ${p.nombre_item}`, 20, yPos);
            doc.setTextColor(100, 100, 100);
            doc.text(`Préstamo: ${p.fecha_prestamo} | Devolución: ${p.fecha_devolucion}`, 25, yPos + 5);
            doc.setTextColor(0, 0, 0);
            yPos += 12;
        });
    }
    
    // Guardar
    doc.save(`Historial_Lector_${data.alumno.replace(/\\s+/g, '_')}.pdf`);
}
