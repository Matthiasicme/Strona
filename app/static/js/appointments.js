// Global variables
let selectedDoctor = null;
let selectedDate = null;
let selectedTime = null;
let availableSlots = [];
let calendar = null;

// Document ready
$(document).ready(function() {
    // Initialize the application
    initApp();
    
    // Event listeners
    $('#changeDoctor').on('click', showDoctorSelection);
    $('#backToCalendar').on('click', showCalendarStep);
    $('#confirmAppointment').on('click', confirmAppointment);
});

// Initialize the application
function initApp() {
    console.log('Initializing application...');
    loadDoctors();
    
    // Initialize calendar after a short delay to ensure DOM is ready
    setTimeout(() => {
        console.log('Initializing calendar...');
        initializeCalendar();
    }, 100);
}

// Load available doctors
function loadDoctors() {
    $.ajax({
        url: '/api/lekarze',
        method: 'GET',
        success: function(response) {
            if (response.status === 'success' && response.data && response.data.length > 0) {
                renderDoctors(response.data);
            } else {
                $('#doctorsList').html('<div class="alert alert-warning">Brak dostępnych lekarzy.</div>');
            }
        },
        error: function(xhr, status, error) {
            console.error('Error loading doctors:', error);
            $('#doctorsList').html('<div class="alert alert-danger">Wystąpił błąd podczas ładowania listy lekarzy.</div>');
        }
    });
}

// Render doctors list
function renderDoctors(doctors) {
    const $doctorsList = $('#doctorsList');
    $doctorsList.empty();
    
    if (doctors.length === 0) {
        $doctorsList.html('<div class="alert alert-warning">Brak dostępnych lekarzy.</div>');
        return;
    }
    
    doctors.forEach(doctor => {
        const doctorCard = `
            <div class="col-md-4 mb-4">
                <div class="card doctor-card h-100" data-doctor-id="${doctor.id}">
                    <div class="card-body">
                        <h5 class="card-title">${doctor.tytul || ''} ${doctor.imie} ${doctor.nazwisko}</h5>
                        <h6 class="card-subtitle mb-2 text-muted">${doctor.specjalizacja || 'Lekarz'}</h6>
                        <p class="card-text">${doctor.opis || 'Brak dodatkowego opisu.'}</p>
                    </div>
                </div>
            </div>
        `;
        $doctorsList.append(doctorCard);
    });
    
    // Add click handler for doctor cards
    $('.doctor-card').on('click', function() {
        const doctorId = $(this).data('doctor-id');
        selectDoctor(doctorId);
    });
}

// Select a doctor
function selectDoctor(doctorId) {
    console.log('Selecting doctor with ID:', doctorId);
    
    // Remove previous selection
    $('.doctor-card').removeClass('selected');
    $(`.doctor-card[data-doctor-id="${doctorId}"]`).addClass('selected');
    
    // Store selected doctor
    $.get(`/api/lekarze/${doctorId}`, function(response) {
        console.log('Received doctor details:', response);
        
        if (response.status === 'success' && response.data) {
            selectedDoctor = response.data;
            console.log('Selected doctor set to:', selectedDoctor);
            
            // Show calendar step
            showCalendarStep();
            
            // Update doctor info
            updateDoctorInfo();
            
            // Load available dates
            loadAvailableDates(doctorId);
            
            // Refresh calendar events
            if (calendar) {
                console.log('Refreshing calendar events...');
                calendar.refetchEvents();
            }
        } else {
            console.error('Invalid response format:', response);
            alert('Nieprawidłowa odpowiedź serwera.');
        }
    }).fail(function(xhr) {
        console.error('Error loading doctor details:', {
            status: xhr.status,
            statusText: xhr.statusText,
            responseText: xhr.responseText
        });
        alert('Wystąpił błąd podczas ładowania danych lekarza. Sprawdź konsolę, aby uzyskać więcej informacji.');
    });
}

// Initialize FullCalendar
function initializeCalendar() {
    console.log('initializeCalendar called');
    const calendarEl = document.getElementById('calendar');
    
    if (!calendarEl) {
        console.error('Calendar element not found!');
        return;
    }
    
    console.log('Calendar element found:', calendarEl);
    
    try {
        console.log('Creating new FullCalendar instance...');
        calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'pl',
        firstDay: 1, // Monday
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        dateClick: function(info) {
            const clickedDate = info.date;
            if (clickedDate < new Date()) {
                alert('Nie można wybrać daty z przeszłości.');
                return;
            }
            selectedDate = clickedDate;
            loadAvailableTimeSlots(selectedDoctor.id, formatDate(clickedDate));
        },
        eventClick: function(info) {
            // Handle event click if needed
        },
        events: function(fetchInfo, successCallback, failureCallback) {
            console.log('Fetching events for period:', fetchInfo.start, 'to', fetchInfo.end);
            
            if (!selectedDoctor) {
                console.log('No doctor selected, returning empty events');
                return successCallback([]);
            }
            
            const url = `/api/terminy?lekarz_id=${selectedDoctor.id}&data_od=${formatDate(fetchInfo.start)}&data_do=${formatDate(fetchInfo.end)}`;
            console.log('Fetching events from:', url);
            
            // Load available dates for the selected doctor
            $.ajax({
                url: url,
                method: 'GET',
                success: function(response) {
                    console.log('Received events response:', response);
                    
                    if (response.status === 'success' && response.terminy) {
                        const events = response.terminy.map(termin => {
                            const event = {
                                title: termin.status === 'wolny' ? 'Wolny termin' : 'Zajęty',
                                start: `${termin.data.split('T')[0]}T${termin.godzina_od}`,
                                end: `${termin.data.split('T')[0]}T${termin.godzina_do}`,
                                allDay: false,
                                backgroundColor: termin.status === 'wolny' ? '#28a745' : '#dc3545',
                                borderColor: termin.status === 'wolny' ? '#218838' : '#c82333',
                                textColor: '#fff',
                                extendedProps: {
                                    available: termin.status === 'wolny',
                                    terminId: termin.id
                                }
                            };
                            console.log('Created event:', event);
                            return event;
                        });
                        
                        console.log('Sending events to calendar:', events);
                        successCallback(events);
                    } else {
                        console.log('No terminy found or error in response');
                        successCallback([]);
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Error loading calendar events:', {
                        status: xhr.status,
                        statusText: xhr.statusText,
                        responseText: xhr.responseText,
                        error: error
                    });
                    failureCallback(error);
                }
            });
        }
    });
    
    console.log('Rendering calendar...');
    calendar.render();
    console.log('FullCalendar initialized successfully');
    
    // Log calendar view info
    console.log('Current view:', calendar.view);
    console.log('Calendar events:', calendar.getEvents());
    
    // Force a refresh of events
    calendar.refetchEvents();
    console.log('Calendar events refetched');
    
    } catch (error) {
        console.error('Error initializing FullCalendar:', error);
        alert('Wystąpił błąd podczas inicjalizacji kalendarza. Sprawdź konsolę przeglądarki, aby uzyskać więcej informacji.');
    }
}

// Load available time slots for a specific date
function loadAvailableTimeSlots(doctorId, date) {
    if (!doctorId || !date) return;
    
    const $availableTimes = $('#availableTimes');
    $availableTimes.html('<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Ładowanie...</span></div>');
    
    $.ajax({
        url: `/api/terminy?lekarz_id=${doctorId}&data_od=${date}&data_do=${date}`,
        method: 'GET',
        success: function(response) {
            $availableTimes.empty();
            
            if (response.status === 'success' && response.terminy && response.terminy.length > 0) {
                availableSlots = response.terminy;
                
                availableSlots.forEach((slot, index) => {
                    const timeSlot = document.createElement('button');
                    timeSlot.className = 'btn btn-outline-primary time-slot';
                    timeSlot.textContent = `${slot.godzina_od} - ${slot.godzina_do}`;
                    timeSlot.dataset.index = index;
                    timeSlot.addEventListener('click', function() {
                        selectTimeSlot(this, index);
                    });
                    $availableTimes.append(timeSlot);
                    $availableTimes.append(' ');
                });
            } else {
                $availableTimes.html('<div class="alert alert-warning">Brak dostępnych terminów w wybranym dniu.</div>');
            }
        },
        error: function(xhr, status, error) {
            console.error('Error loading time slots:', error);
            $availableTimes.html('<div class="alert alert-danger">Wystąpił błąd podczas ładowania dostępnych terminów.</div>');
        }
    });
}

// Select a time slot
function selectTimeSlot(element, index) {
    $('.time-slot').removeClass('btn-primary').addClass('btn-outline-primary');
    $(element).removeClass('btn-outline-primary').addClass('btn-primary');
    
    selectedTime = availableSlots[index];
    showAppointmentDetails();
}

// Show appointment details step
function showAppointmentDetails() {
    if (!selectedDoctor || !selectedDate || !selectedTime) return;
    
    const appointmentDate = new Date(selectedDate);
    const formattedDate = appointmentDate.toLocaleDateString('pl-PL', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    
    const summaryHtml = `
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Podsumowanie wizyty</h5>
                <div class="mb-3">
                    <strong>Lekarz:</strong> ${selectedDoctor.tytul || ''} ${selectedDoctor.imie} ${selectedDoctor.nazwisko}
                </div>
                <div class="mb-3">
                    <strong>Data:</strong> ${formattedDate}
                </div>
                <div>
                    <strong>Godzina:</strong> ${selectedTime.godzina_od} - ${selectedTime.godzina_do}
                </div>
            </div>
        </div>
    `;
    
    $('#appointmentSummary').html(summaryHtml);
    
    // Show the appointment details section
    $('#calendarStep').hide();
    $('#appointmentDetails').fadeIn();
}

// Confirm appointment
function confirmAppointment() {
    if (!selectedDoctor || !selectedDate || !selectedTime) {
        alert('Proszę wybrać wszystkie wymagane dane.');
        return;
    }
    
    const notes = $('#appointmentNotes').val().trim();
    
    // Prepare the appointment data
    const appointmentData = {
        termin_id: selectedTime.id,
        lekarz_id: selectedDoctor.id,
        opis: notes || null
    };
    
    // Show loading state
    const $confirmBtn = $('#confirmAppointment');
    const originalBtnText = $confirmBtn.html();
    $confirmBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Zapisywanie...');
    
    // Send the request to book the appointment
    $.ajax({
        url: '/api/wizyty',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(appointmentData),
        success: function(response) {
            if (response.status === 'success') {
                showSuccessMessage(response.message || 'Twoja wizyta została umówiona pomyślnie!');
            } else {
                alert(response.message || 'Wystąpił błąd podczas umawiania wizyty.');
            }
        },
        error: function(xhr) {
            let errorMessage = 'Wystąpił błąd podczas umawiania wizyty.';
            if (xhr.responseJSON && xhr.responseJSON.message) {
                errorMessage = xhr.responseJSON.message;
            }
            alert(errorMessage);
        },
        complete: function() {
            $confirmBtn.prop('disabled', false).html(originalBtnText);
        }
    });
}

// Show success message
function showSuccessMessage(message) {
    $('#successMessage').text(message);
    const successModal = new bootstrap.Modal(document.getElementById('successModal'));
    successModal.show();
    
    // Reset the form after showing the success message
    setTimeout(() => {
        resetForm();
    }, 5000);
}

// Reset the form
function resetForm() {
    selectedDoctor = null;
    selectedDate = null;
    selectedTime = null;
    availableSlots = [];
    
    // Reset form fields
    $('#appointmentNotes').val('');
    
    // Reset UI
    $('.doctor-card').removeClass('selected');
    $('#availableTimes').empty();
    
    // Go back to the first step
    showDoctorSelection();
    
    // Refresh the calendar
    if (calendar) {
        calendar.refetchEvents();
    }
}

// Show doctor selection step
function showDoctorSelection() {
    $('#calendarStep').hide();
    $('#appointmentDetails').hide();
    $('#selectDoctorStep').fadeIn();
}

// Show calendar step
function showCalendarStep() {
    $('#selectDoctorStep').hide();
    $('#appointmentDetails').hide();
    $('#calendarStep').fadeIn();
    
    // Refresh the calendar
    if (calendar) {
        calendar.refetchEvents();
    }
}

// Update doctor info in the calendar step
function updateDoctorInfo() {
    if (!selectedDoctor) return;
    
    const doctorInfoHtml = `
        <div class="alert alert-info mb-4">
            <h6>Wybrany lekarz:</h6>
            <p class="mb-0">${selectedDoctor.tytul || ''} ${selectedDoctor.imie} ${selectedDoctor.nazwisko}<br>
            <small class="text-muted">${selectedDoctor.specjalizacja || ''}</small></p>
        </div>
    `;
    
    $('#doctorInfo').html(doctorInfoHtml);
}

// Format date to YYYY-MM-DD
function formatDate(date) {
    const d = new Date(date);
    let month = '' + (d.getMonth() + 1);
    let day = '' + d.getDate();
    const year = d.getFullYear();

    if (month.length < 2) month = '0' + month;
    if (day.length < 2) day = '0' + day;

    return [year, month, day].join('-');
}

// Load available dates for a doctor
function loadAvailableDates(doctorId) {
    if (!doctorId || !calendar) return;
    
    // This will trigger the events function in the calendar
    calendar.refetchEvents();
}
