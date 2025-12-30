const { useState, useEffect, useMemo } = React;

// --- Icons ---
const Icon = ({ name, size = 18, className = "" }) => {
    useEffect(() => {
        if (window.lucide) window.lucide.createIcons();
    }, [name]);
    return <i data-lucide={name} style={{ width: size, height: size }} className={className}></i>;
};

// --- Calendar Logic ---
const { format, startOfMonth, endOfMonth, startOfWeek, endOfWeek, addDays, addMonths, subMonths, isSameMonth, isSameDay, parseISO } = dateFns;

const CalendarView = ({ appointments, onClose }) => {
    const [currentMonth, setCurrentMonth] = useState(new Date());

    const calendarDays = useMemo(() => {
        const monthStart = startOfMonth(currentMonth);
        const monthEnd = endOfMonth(monthStart);
        const startDate = startOfWeek(monthStart);
        const endDate = endOfWeek(monthEnd);

        const days = [];
        let day = startDate;
        while (day <= endDate) {
            days.push(day);
            day = addDays(day, 1);
        }
        return days;
    }, [currentMonth]);

    const nextMonth = () => setCurrentMonth(addMonths(currentMonth, 1));
    const prevMonth = () => setCurrentMonth(subMonths(currentMonth, 1));

    // Helper to find appointments for a day
    const getApptsForDay = (day) => {
        return appointments.filter(a => {
            // Assuming a.date is YYYY-MM-DD
            // or parsing a.start_time
            const dStr = format(day, "yyyy-MM-dd");
            return a.date === dStr;
        });
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 animate-fade-in">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-slate-800">
                    {format(currentMonth, "MMMM yyyy")}
                </h2>
                <div className="flex items-center gap-2">
                    <button onClick={prevMonth} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
                        <Icon name="chevron-left" />
                    </button>
                    <button onClick={nextMonth} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
                        <Icon name="chevron-right" />
                    </button>
                    <button onClick={onClose} className="ml-4 text-sm text-sky-500 font-medium hover:text-sky-600 transition-colors">
                        Back to List
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-7 gap-1 text-center mb-2">
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(d => (
                    <div key={d} className="text-xs font-semibold text-slate-400 uppercase tracking-wide py-2">{d}</div>
                ))}
            </div>

            <div className="grid grid-cols-7 gap-1">
                {calendarDays.map((day, idx) => {
                    const isCurrentMonth = isSameMonth(day, currentMonth);
                    const dayAppts = getApptsForDay(day);
                    const hasAppts = dayAppts.length > 0;
                    const isToday = isSameDay(day, new Date());

                    return (
                        <div
                            key={idx}
                            className={`
                 relative min-h-[80px] p-2 rounded-lg border border-transparent hover:border-sky-200 hover:bg-sky-50 transition-all cursor-pointer flex flex-col items-center justify-start gap-1
                 ${!isCurrentMonth ? "bg-slate-50 text-slate-400" : "bg-white text-slate-700"}
                 ${isToday ? "ring-2 ring-sky-500 ring-offset-2" : ""}
               `}
                            onClick={() => {
                                if (hasAppts) alert(`${dayAppts.length} appointments on ${format(day, 'MMM d')}: \n` + dayAppts.map(a => `${a.start_time.slice(0, 5)} - ${a.client_name}`).join('\n'));
                            }}
                        >
                            <span className={`text-sm font-medium ${!isCurrentMonth ? "text-slate-300" : ""}`}>{format(day, "d")}</span>

                            {hasAppts && (
                                <div className="flex gap-1 flex-wrap justify-center mt-1">
                                    {dayAppts.map((_, i) => (
                                        <div key={i} className="w-1.5 h-1.5 rounded-full bg-sky-500" title="Appointment"></div>
                                    ))}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

// --- Add Appointment Form ---
const AddAppointmentForm = ({ onCancel, onSave }) => {
    const [formData, setFormData] = useState({
        clientName: "",
        date: "",
        time: "",
        service: "Haircut (Standard)"
    });
    const [isFading, setIsFading] = useState(true); // Start visible immediately, handled by parent transition usually. But let's fade IN.

    useEffect(() => {
        setIsFading(false); // Trigger fade in
    }, []);

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        onSave(formData);
    };

    return (
        <form onSubmit={handleSubmit} className={`bg-white rounded-xl shadow-sm border border-sky-100 p-6 transition-all duration-300 transform ${isFading ? 'opacity-0 scale-95' : 'opacity-100 scale-100'}`}>
            <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                <Icon name="calendar-plus" className="text-sky-500" /> New Appointment
            </h3>

            <div className="space-y-4">
                <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">Client Name</label>
                    <input name="clientName" required type="text" className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:outline-none transition-all" placeholder="e.g. John Doe" value={formData.clientName} onChange={handleChange} />
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">Date</label>
                        <input name="date" required type="date" className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:outline-none transition-all" value={formData.date} onChange={handleChange} />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">Time</label>
                        <input name="time" required type="time" className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:outline-none transition-all" value={formData.time} onChange={handleChange} />
                    </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">Service Type</label>
                    <select name="service" className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 focus:outline-none transition-all bg-white" value={formData.service} onChange={handleChange}>
                        <option>Haircut (Standard)</option>
                        <option>Beard Trim</option>
                        <option>Full Service</option>
                    </select>
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 mt-2">
                    <button type="button" onClick={onCancel} className="px-4 py-2 text-slate-500 hover:text-slate-700 font-medium transition-colors">
                        Cancel
                    </button>
                    <button type="submit" className="px-6 py-2 bg-gradient-to-r from-sky-400 to-sky-600 text-white font-bold rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-0.5 transition-all">
                        Save Appointment
                    </button>
                </div>
            </div>
        </form>
    );
};

// --- Main List View ---
const AppointmentList = ({ appointments, onAddClick, onViewAllClick }) => {
    return (
        <div>
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-bold text-slate-800">Upcoming Appointments</h3>
                <div className="flex gap-4 items-center">
                    <button onClick={onAddClick} className="hidden md:block btn-sm bg-sky-50 text-sky-600 hover:bg-sky-100 px-3 py-1 rounded-md text-sm font-medium transition-colors">
                        + Add
                    </button>
                    <button onClick={onViewAllClick} className="text-sm text-sky-500 hover:text-sky-600 font-medium transition-colors">
                        View All
                    </button>
                </div>
            </div>

            {appointments.length === 0 ? (
                <div className="bg-slate-50 border border-dashed border-slate-300 rounded-xl p-8 flex flex-col items-center justify-center text-center">
                    <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-sm mb-3">
                        <span className="text-2xl">📅</span>
                    </div>
                    <p className="text-slate-500 mb-4">No upcoming appointments.</p>

                    {/* The "Add Appointment" button transition requires replacing THIS button */}
                    <button
                        onClick={onAddClick}
                        className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white rounded-lg shadow-sm font-medium transition-all"
                    >
                        Add Appointment
                    </button>
                </div>
            ) : (
                <div className="space-y-3">
                    {/* Desktop Table - Hidden on Mobile via CSS usually, but here we can manage responsiveness too or just render standard structure */}
                    <div className="overflow-x-auto bg-white rounded-xl shadow-sm border border-slate-100 hidden md:block">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="bg-slate-50 border-b border-slate-100 text-xs text-slate-500 uppercase tracking-wider">
                                    <th className="p-4 font-semibold">Time</th>
                                    <th className="p-4 font-semibold">Client</th>
                                    <th className="p-4 font-semibold">Service</th>
                                    <th className="p-4 font-semibold">Status</th>
                                    <th className="p-4 font-semibold">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                                {appointments.map((appt, i) => (
                                    <tr key={i} className="hover:bg-slate-50 transition-colors">
                                        <td className="p-4">
                                            <div className="font-bold text-slate-800">{appt.start_time.slice(0, 5)}</div>
                                            <div className="text-xs text-slate-400">{appt.date}</div>
                                        </td>
                                        <td className="p-4 text-slate-700 font-medium">{appt.client_name}</td>
                                        <td className="p-4 text-slate-600 text-sm">Haircut (Standard)</td>
                                        <td className="p-4"><span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-bold rounded-full">Confirmed</span></td>
                                        <td className="p-4">
                                            <button className="p-1 hover:bg-slate-200 rounded transition-colors text-slate-400 hover:text-slate-600">
                                                <Icon name="pencil" size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Mobile Cards */}
                    <div className="md:hidden space-y-3">
                        {appointments.map((appt, i) => (
                            <div key={i} className="bg-white/60 backdrop-blur-sm border border-sky-100 rounded-xl p-4 shadow-sm">
                                <div className="flex justify-between items-center mb-2">
                                    <span className="font-bold text-slate-800 text-lg">{appt.start_time.slice(0, 5)}</span>
                                    <span className="px-2 py-0.5 bg-green-100 text-green-700 text-[10px] uppercase font-bold rounded-full tracking-wide">Confirmed</span>
                                </div>
                                <div className="text-base font-medium text-slate-800 mb-1">{appt.client_name}</div>
                                <div className="text-sm text-slate-500 flex justify-between items-center">
                                    <span>{appt.date} • Standard Cut</span>
                                    <button className="text-slate-400 hover:text-sky-500">
                                        <Icon name="pencil" size={16} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

// --- App Component ---
const DashboardApp = () => {
    const [view, setView] = useState("list"); // list, add, calendar
    const [appointments, setAppointments] = useState([]);
    const [showAddTransition, setShowAddTransition] = useState(false);

    useEffect(() => {
        // Load data from hidden script tag
        try {
            const el = document.getElementById("appt-data");
            if (el) {
                const data = JSON.parse(el.textContent);
                setAppointments(data);
            }
        } catch (e) {
            console.error("Failed to parse appt data", e);
        }
    }, []);

    const handleAddClick = () => {
        // Trigger exit animation for button if we were isolating it, but here we switch view.
        // We'll use a simple state switch with CSS transition wrapper
        setView("add");
    };

    const handleSaveAppointment = (newItem) => {
        // Add to local state
        const newAppt = {
            ...newItem,
            start_time: newItem.time, // simplified mapping
            client_name: newItem.clientName,
            status: "Confirmed"
        };
        // Sort
        const updated = [...appointments, newAppt].sort((a, b) => (a.date + a.time) > (b.date + b.time) ? 1 : -1);
        setAppointments(updated);
        setView("list");
    };

    return (
        <div className="relative min-h-[300px]">
            {/* View specific render with transitions */}
            {view === "list" && (
                <AppointmentList
                    appointments={appointments}
                    onAddClick={handleAddClick}
                    onViewAllClick={() => setView("calendar")}
                />
            )}

            {view === "add" && (
                <AddAppointmentForm
                    onCancel={() => setView("list")}
                    onSave={handleSaveAppointment}
                />
            )}

            {view === "calendar" && (
                <CalendarView
                    appointments={appointments}
                    onClose={() => setView("list")}
                />
            )}
        </div>
    );
};

// Render
const root = document.getElementById("react-appointments-root");
if (root) {
    ReactDOM.createRoot(root).render(<DashboardApp />);
}
