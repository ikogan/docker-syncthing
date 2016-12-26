'use strict';

angular.module('gaea',['ngAnimate', 'ngAria', 'ngSanitize'])
    .config(function($locationProvider) {
        $locationProvider.html5Mode(true);
    }).controller('MainController', function($scope, $http, $window, $timeout) {
        var self = this;

        /**
         * Tiny function that will wait for the container to actually
         * be available be reloading the page and loading Syncthing as
         * a result.
         */
        self.checkStatus = function() {
            $http.get('/syncthing').then(function(response) {
                $window.location.reload();
            }).catch(function(response) {
                $timeout(self.checkStatus, 500);
            });
        }

        /**
         * On initialization, immediately call the API. Errors should be gracefully
         * displayed and the page should be reloaded when finished.
         */
        self.init = function () {
            $http.post('/syncthing/api/create-container').then(function (response) {
                switch(response.status) {
                    case 201: self.checkStatus(); break;
                    default: self.error = 'Unhandled successful API response: ' + response.status; break;
                }
            }).catch(function (response) {
                switch(response.status) {
                    case 401: $window.location.reload(); break;
                    case 403: self.error = "Access Denied"; break;
                    case 404: self.error = "Syncthing API Not Found"; break;
                    case 409: self.error = "Container for your user already exists." +
                        " This requires manual fixing."; break;
                    default:
                        if(typeof response.data === 'object') {
                            self.error = response.data.message;
                        } else{
                            self.error = 'Unhandled Internal Server Error';
                        }
                        break;
                }
            });
        }
    });
