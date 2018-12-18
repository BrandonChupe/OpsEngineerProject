$(function() {
    $('#button').on('click', function() {
        $.ajax({
            url: '/',
            data: $('form').serialize(),
            type: 'POST',
            success: function(response) {
                document.getElementById("#body").innerHTML = $('body').response
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            }
        });
    });
});
