var viewModel ={
    policyNumber: ko.observable().extend({
        pattern: {
            message: "Only letters, numbers, and spaces are allowed."
        }
    }),
    policyDate: ko.observable().extend({
        required: true
    })
}

ko.applyBindings(viewModel);
